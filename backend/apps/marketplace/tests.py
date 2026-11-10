from decimal import Decimal

from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import Profile, User

from .models import Category, Job, Proposal, Skill

PW = "Sturdy-Pass-4821"
COVER = "I have built many projects like this and can deliver on time."


def make_user(email, role):
    user = User.objects.create_user(email=email, password=PW, role=role)
    Profile.objects.create(user=user, full_name=email.split("@")[0].title())
    return user


class Base(APITestCase):
    def setUp(self):
        cache.clear()  # reset throttle counters
        self.owner = make_user("owner@example.com", "client")
        self.other_client = make_user("other@example.com", "client")
        self.freelancer = make_user("free@example.com", "freelancer")
        self.freelancer2 = make_user("free2@example.com", "freelancer")
        self.web = Category.objects.create(name="Web", slug="web")
        self.design = Category.objects.create(name="Design", slug="design")
        self.python = Skill.objects.create(name="Python", slug="python")
        self.job = self.make_job()

    def make_job(self, **overrides):
        data = dict(client=self.owner, category=self.web, title="Build API",
                    description="Need a Django API", budget_type="fixed",
                    budget_amount=Decimal("500"), currency="USD")
        data.update(overrides)
        return Job.objects.create(**data)

    def login(self, user):
        self.client.force_login(user)


class JobTests(Base):
    def test_feed_is_public_and_lists_only_open_jobs(self):
        self.make_job(title="Closed one", status="in_progress")
        resp = self.client.get("/api/jobs/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([j["title"] for j in resp.data["results"]], ["Build API"])

    def test_feed_filters(self):
        self.make_job(title="Logo design", description="Need a logo", category=self.design,
                      budget_amount=Decimal("100"))

        def titles(query):
            return sorted(j["title"] for j in self.client.get(f"/api/jobs/{query}").data["results"])

        self.assertEqual(titles("?category=design"), ["Logo design"])
        self.assertEqual(titles("?min=300"), ["Build API"])
        self.assertEqual(titles("?max=300"), ["Logo design"])
        self.assertEqual(titles("?q=logo"), ["Logo design"])
        self.assertEqual(self.client.get("/api/jobs/?min=abc").status_code, 400)

    def test_feed_never_exposes_emails(self):
        resp = self.client.get("/api/jobs/")
        self.assertNotIn("owner@example.com", str(resp.data))

    def test_only_clients_can_post_jobs(self):
        body = {"title": "New job", "description": "Details here", "budget_type": "fixed",
                "budget_amount": "250.00", "currency": "USD",
                "category_id": self.web.id, "skill_ids": [self.python.id]}
        self.assertEqual(self.client.post("/api/jobs/", body, format="json").status_code, 403)
        self.login(self.freelancer)
        self.assertEqual(self.client.post("/api/jobs/", body, format="json").status_code, 403)
        self.login(self.owner)
        resp = self.client.post("/api/jobs/", body, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Job.objects.get(pk=resp.data["id"]).client, self.owner)

    def test_zero_budget_rejected(self):
        self.login(self.owner)
        body = {"title": "Bad", "description": "x", "budget_type": "fixed",
                "budget_amount": "0", "category_id": self.web.id}
        self.assertEqual(self.client.post("/api/jobs/", body, format="json").status_code, 400)

    def test_only_owner_can_edit(self):
        self.login(self.other_client)
        resp = self.client.patch(f"/api/jobs/{self.job.id}/", {"title": "Hacked"}, format="json")
        self.assertEqual(resp.status_code, 403)
        self.login(self.owner)
        resp = self.client.patch(f"/api/jobs/{self.job.id}/", {"title": "Renamed"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, "Renamed")

    def test_cannot_edit_job_once_in_progress(self):
        self.job.status = "in_progress"
        self.job.save()
        self.login(self.owner)
        resp = self.client.patch(f"/api/jobs/{self.job.id}/", {"title": "Late edit"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_delete_cancels_instead_of_deleting(self):
        self.login(self.owner)
        self.assertEqual(self.client.delete(f"/api/jobs/{self.job.id}/").status_code, 204)
        self.job.refresh_from_db()  # still exists
        self.assertEqual(self.job.status, "cancelled")
        self.assertEqual(self.client.get("/api/jobs/").data["count"], 0)


class ProposalTests(Base):
    def propose(self, user, job=None, **overrides):
        self.login(user)
        body = {"bid_amount": "450.00", "delivery_days": 14, "cover_letter": COVER}
        body.update(overrides)
        return self.client.post(f"/api/jobs/{(job or self.job).id}/proposals/", body, format="json")

    def test_freelancer_can_submit_proposal(self):
        resp = self.propose(self.freelancer)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Proposal.objects.count(), 1)
        self.assertNotIn("free@example.com", str(resp.data))

    def test_duplicate_proposal_rejected(self):
        self.assertEqual(self.propose(self.freelancer).status_code, 201)
        self.assertEqual(self.propose(self.freelancer).status_code, 400)
        self.assertEqual(Proposal.objects.count(), 1)

    def test_cannot_propose_on_closed_job(self):
        self.job.status = "in_progress"
        self.job.save()
        self.assertEqual(self.propose(self.freelancer).status_code, 400)

    def test_client_cannot_submit_proposal(self):
        self.assertEqual(self.propose(self.owner).status_code, 403)

    def test_anonymous_cannot_propose(self):
        resp = self.client.post(f"/api/jobs/{self.job.id}/proposals/", {}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_only_owner_sees_proposals(self):
        self.propose(self.freelancer)
        url = f"/api/jobs/{self.job.id}/proposals/"
        self.login(self.owner)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["results"]), 1)
        self.login(self.other_client)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login(self.freelancer)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_accept_proposal(self):
        p1 = self.propose(self.freelancer).data["id"]
        p2 = self.propose(self.freelancer2).data["id"]
        self.login(self.owner)
        resp = self.client.post(f"/api/proposals/{p1}/accept/")
        self.assertEqual(resp.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "in_progress")
        self.assertEqual(Proposal.objects.get(pk=p1).status, "accepted")
        self.assertEqual(Proposal.objects.get(pk=p2).status, "rejected")

    def test_only_owner_can_accept(self):
        pid = self.propose(self.freelancer).data["id"]
        self.login(self.other_client)
        self.assertEqual(self.client.post(f"/api/proposals/{pid}/accept/").status_code, 404)
        self.assertEqual(Proposal.objects.get(pk=pid).status, "pending")

    def test_cannot_accept_twice_or_accept_a_second_proposal(self):
        p1 = self.propose(self.freelancer).data["id"]
        p2 = self.propose(self.freelancer2).data["id"]
        self.login(self.owner)
        self.assertEqual(self.client.post(f"/api/proposals/{p1}/accept/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/proposals/{p1}/accept/").status_code, 400)
        self.assertEqual(self.client.post(f"/api/proposals/{p2}/accept/").status_code, 400)
        self.assertEqual(Proposal.objects.filter(status="accepted").count(), 1)

    def test_reject_proposal(self):
        pid = self.propose(self.freelancer).data["id"]
        self.login(self.owner)
        self.assertEqual(self.client.post(f"/api/proposals/{pid}/reject/").status_code, 200)
        self.assertEqual(Proposal.objects.get(pk=pid).status, "rejected")
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "open")

    def test_freelancer_sees_only_own_proposals(self):
        self.propose(self.freelancer)
        self.login(self.freelancer)
        self.assertEqual(len(self.client.get("/api/proposals/mine/").data["results"]), 1)
        self.login(self.freelancer2)
        self.assertEqual(len(self.client.get("/api/proposals/mine/").data["results"]), 0)
        
        
from .models import Review


class ReviewTests(Base):
    def hire(self):
        """The freelancer proposes and the client accepts. Leaves the client logged in."""
        self.login(self.freelancer)
        body = {"bid_amount": "450.00", "delivery_days": 14, "cover_letter": COVER}
        pid = self.client.post(f"/api/jobs/{self.job.id}/proposals/", body, format="json").data["id"]
        self.login(self.owner)
        self.client.post(f"/api/proposals/{pid}/accept/")

    def test_owner_can_complete_job_in_progress(self):
        self.hire()
        resp = self.client.post(f"/api/jobs/{self.job.id}/complete/")
        self.assertEqual(resp.status_code, 200)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "completed")

    def test_cannot_complete_open_job(self):
        self.login(self.owner)
        self.assertEqual(self.client.post(f"/api/jobs/{self.job.id}/complete/").status_code, 400)

    def test_only_owner_can_complete(self):
        self.hire()
        self.login(self.other_client)
        self.assertEqual(self.client.post(f"/api/jobs/{self.job.id}/complete/").status_code, 404)
        self.login(self.freelancer)
        self.assertEqual(self.client.post(f"/api/jobs/{self.job.id}/complete/").status_code, 403)

    def test_full_review_flow(self):
        self.hire()
        self.client.post(f"/api/jobs/{self.job.id}/complete/")
        resp = self.client.post(f"/api/jobs/{self.job.id}/reviews/",
                                {"rating": 5, "comment": "Great work"}, format="json")
        self.assertEqual(resp.status_code, 201)
        review = Review.objects.get()
        self.assertEqual(review.reviewer, self.owner)
        self.assertEqual(review.reviewee, self.freelancer)  # taken from the accepted proposal
        self.client.logout()
        pid = self.freelancer.profile.id
        reviews = self.client.get(f"/api/talent/{pid}/reviews/")
        self.assertEqual(reviews.data["count"], 1)
        self.assertNotIn("owner@example.com", str(reviews.data))
        talent = self.client.get(f"/api/talent/{pid}/").data
        self.assertEqual(float(talent["avg_rating"]), 5.0)
        self.assertEqual(talent["review_count"], 1)

    def test_cannot_review_before_completion(self):
        self.hire()
        resp = self.client.post(f"/api/jobs/{self.job.id}/reviews/", {"rating": 4}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)

    def test_cannot_review_twice(self):
        self.hire()
        self.client.post(f"/api/jobs/{self.job.id}/complete/")
        url = f"/api/jobs/{self.job.id}/reviews/"
        self.assertEqual(self.client.post(url, {"rating": 4}, format="json").status_code, 201)
        self.assertEqual(self.client.post(url, {"rating": 1}, format="json").status_code, 400)
        self.assertEqual(Review.objects.count(), 1)

    def test_only_job_owner_can_review(self):
        self.hire()
        self.client.post(f"/api/jobs/{self.job.id}/complete/")
        url = f"/api/jobs/{self.job.id}/reviews/"
        self.login(self.other_client)
        self.assertEqual(self.client.post(url, {"rating": 5}, format="json").status_code, 404)
        self.login(self.freelancer)
        self.assertEqual(self.client.post(url, {"rating": 5}, format="json").status_code, 403)

    def test_rating_must_be_1_to_5(self):
        self.hire()
        self.client.post(f"/api/jobs/{self.job.id}/complete/")
        url = f"/api/jobs/{self.job.id}/reviews/"
        self.assertEqual(self.client.post(url, {"rating": 0}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"rating": 6}, format="json").status_code, 400)