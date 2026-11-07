from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .models import Job, Proposal


def _fail(message):
    raise ValidationError({"detail": message})


@transaction.atomic
def submit_proposal(*, job_id, freelancer, bid_amount, delivery_days, cover_letter):
    # Lock the job row so two simultaneous submissions can't both pass the checks
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
    """Lock the job, check ownership, and return (job, proposal). Call inside a transaction."""
    proposal = Proposal.objects.filter(pk=proposal_id).first()
    if proposal is None:
        raise NotFound("Proposal not found.")
    job = Job.objects.select_for_update().get(pk=proposal.job_id)
    if job.client_id != client.id:
        raise NotFound("Proposal not found.")  # 404, not 403: don't reveal that it exists
    proposal.refresh_from_db()  # re-read after the lock, in case someone changed it first
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