from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .models import Job, Proposal, Review


def _fail(message):
    raise ValidationError({"detail": message})


@transaction.atomic
def submit_proposal(*, job_id, freelancer, bid_amount, delivery_days, cover_letter):
    job = Job.objects.select_for_update().filter(pk=job_id).first()
    if job is None:
        raise NotFound("Job not found.")
    if job.client_id == freelancer.id:
        raise PermissionDenied("You cannot bid on your own job.")
    if job.status != Job.Status.OPEN:
        _fail("This job is no longer accepting proposals.")
    if Proposal.objects.filter(job=job, freelancer=freelancer).exists():
        _fail("You already submitted a proposal for this job.")
    return Proposal.objects.create(
        job=job, freelancer=freelancer, bid_amount=bid_amount,
        delivery_days=delivery_days, cover_letter=cover_letter,
    )


def _lock_pending_proposal(proposal_id, client):
    proposal = Proposal.objects.filter(pk=proposal_id).first()
    if proposal is None:
        raise NotFound("Proposal not found.")
    job = Job.objects.select_for_update().get(pk=proposal.job_id)
    if job.client_id != client.id:
        raise NotFound("Proposal not found.")
    proposal.refresh_from_db()
    if proposal.status != Proposal.Status.PENDING:
        _fail("Only pending proposals can be changed.")
    return job, proposal


@transaction.atomic
def accept_proposal(*, proposal_id, client):
    job, proposal = _lock_pending_proposal(proposal_id, client)
    if job.status != Job.Status.OPEN:
        _fail("This job is not open.")
    proposal.status = Proposal.Status.ACCEPTED
    proposal.save(update_fields=["status"])
    job.proposals.exclude(pk=proposal.pk).filter(status=Proposal.Status.PENDING).update(
        status=Proposal.Status.REJECTED
    )
    job.status = Job.Status.IN_PROGRESS
    job.save(update_fields=["status", "updated_at"])
    return proposal


@transaction.atomic
def reject_proposal(*, proposal_id, client):
    _, proposal = _lock_pending_proposal(proposal_id, client)
    proposal.status = Proposal.Status.REJECTED
    proposal.save(update_fields=["status"])
    return proposal


@transaction.atomic
def complete_job(*, job_id, client):
    job = Job.objects.select_for_update().filter(pk=job_id).first()
    if job is None or job.client_id != client.id:
        raise NotFound("Job not found.")
    if job.status != Job.Status.IN_PROGRESS:
        _fail("Only jobs in progress can be marked complete.")
    job.status = Job.Status.COMPLETED
    job.save(update_fields=["status", "updated_at"])
    return job


@transaction.atomic
def submit_review(*, job_id, client, rating, comment):
    job = Job.objects.select_for_update().filter(pk=job_id).first()
    if job is None or job.client_id != client.id:
        raise NotFound("Job not found.")
    if job.status != Job.Status.COMPLETED:
        _fail("You can review only after the job is completed.")
    hired = job.proposals.filter(status=Proposal.Status.ACCEPTED).select_related("freelancer").first()
    if hired is None:
        _fail("This job has no hired freelancer.")
    if Review.objects.filter(job=job, reviewer=client).exists():
        _fail("You already reviewed this job.")
    return Review.objects.create(
        job=job, reviewer=client, reviewee=hired.freelancer, rating=rating, comment=comment
    )
    
    
@transaction.atomic
def withdraw_proposal(*, proposal_id, freelancer):
    # Only your own proposals: anyone else's id gives a 404
    proposal = Proposal.objects.filter(pk=proposal_id, freelancer=freelancer).first()
    if proposal is None:
        raise NotFound("Proposal not found.")
    # Lock the job row like accept does, so withdraw and accept can't both win
    Job.objects.select_for_update().get(pk=proposal.job_id)
    proposal.refresh_from_db()
    if proposal.status != Proposal.Status.PENDING:
        _fail("Only pending proposals can be withdrawn.")
    proposal.status = Proposal.Status.WITHDRAWN
    proposal.save(update_fields=["status"])
    return proposal