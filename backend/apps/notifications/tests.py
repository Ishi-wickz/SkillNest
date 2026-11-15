from decimal import Decimal
from types import SimpleNamespace

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.cache import cache
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from apps.accounts.models import Profile, User
from apps.marketplace.models import Category, Job

from . import services
from .consumers import NotificationConsumer
from .models import Notification, NotificationPreference

PW = "Sturdy-Pass-4821"
COVER = "I have built many projects like this and can deliver on time."
K = Notification.Kind


def make_user(email, role):
    user = User.objects.create_user(email=email, password=PW, role=role, email_verified=True)
    Profile.objects.create(user=user, full_name=email.split("@")[0].title())
    return user


def build_world():
    w = SimpleNamespace()
    w.owner = make_user("owner@example.com", "client")
    w.free = make_user("free@example.com", "freelancer")
    w.free2 = make_user("free2@example.com", "freelancer")
    cat = Category.objects.create(name="Web", slug="web")
    w.job = Job.objects.create(client=w.owner, category=cat, title="Build API",
                               description="Need a Django API", budget_type="fixed",
                               budget_amount=Decimal("500"), currency="USD")
    return w


class Base(APITestCase):
    def setUp(self):
        cache.clear()  # resets the email cap
        self.w = build_world()

    def propose(self, user):
        self.client.force_login(user)
        body = {"bid_amount": "450.00", "delivery_days": 14, "cover_letter": COVER}
        resp = self.client.post(f"/api/jobs/{self.w.job.id}/proposals/", body, format="json")
        self.assertEqual(resp.status_code, 201)
        return resp.data["id"]

    def kinds(self, user):
        return sorted(Notification.objects.filter(user=user).values_list("kind", flat=True))


class NotificationApiTests(Base):
    def test_requires_login(self):
        for url in ("/api/notifications/", "/api/notifications/unread/", "/api/notifications/settings/"):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post("/api/notifications/read-all/").status_code, 403)

    def test_proposal_notifies_only_the_client(self):
        self.propose(self.w.free)
        self.assertEqual(self.kinds(self.w.owner), ["proposal_received"])
        self.assertEqual(self.kinds(self.w.free), [])
        self.client.force_login(self.w.owner)
        data = self.client.get("/api/notifications/").data
        self.assertEqual(data["count"], 1)
        self.assertIn("Free sent a proposal", data["results"][0]["message"])
        self.assertNotIn("example.com", str(data))
        self.assertEqual(self.client.get("/api/notifications/unread/").data["count"], 1)

    def test_accept_notifies_winner_and_losers(self):
        p1 = self.propose(self.w.free)
        self.propose(self.w.free2)
        self.client.force_login(self.w.owner)
        self.assertEqual(self.client.post(f"/api/proposals/{p1}/accept/").status_code, 200)
        self.assertEqual(self.kinds(self.w.free), ["proposal_accepted"])
        self.assertEqual(self.kinds(self.w.free2), ["proposal_rejected"])

    def test_reject_and_withdraw(self):
        p1 = self.propose(self.w.free)
        self.client.force_login(self.w.owner)
        self.client.post(f"/api/proposals/{p1}/reject/")
        self.assertEqual(self.kinds(self.w.free), ["proposal_rejected"])
        p2 = self.propose(self.w.free2)  # leaves free2 logged in
        self.assertEqual(self.client.post(f"/api/proposals/{p2}/withdraw/").status_code, 200)
        self.assertIn("proposal_withdrawn", self.kinds(self.w.owner))

    def test_complete_and_review_notify_the_freelancer(self):
        p1 = self.propose(self.w.free)
        self.client.force_login(self.w.owner)
        self.client.post(f"/api/proposals/{p1}/accept/")
        self.assertEqual(self.client.post(f"/api/jobs/{self.w.job.id}/complete/").status_code, 200)
        resp = self.client.post(f"/api/jobs/{self.w.job.id}/reviews/",
                                {"rating": 5, "comment": "Great"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(self.kinds(self.w.free), ["job_completed", "proposal_accepted", "review_received"])
        note = Notification.objects.get(user=self.w.free, kind="review_received")
        self.assertEqual(note.url, f"/talent/{self.w.free.profile.id}/")
        self.assertIn("5-star", note.message)

    def test_mark_one_read_and_other_users_get_404(self):
        self.propose(self.w.free)
        note = Notification.objects.get(user=self.w.owner)
        self.client.force_login(self.w.free2)
        self.assertEqual(self.client.post(f"/api/notifications/{note.id}/read/").status_code, 404)
        self.client.force_login(self.w.owner)
        resp = self.client.post(f"/api/notifications/{note.id}/read/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["read"])
        self.assertEqual(self.client.get("/api/notifications/unread/").data["count"], 0)

    def test_mark_all_read_touches_only_my_notifications(self):
        for i in range(3):
            services.notify(user=self.w.owner, kind=K.JOB_COMPLETED, message=f"n{i}", url="/dashboard/")
        services.notify(user=self.w.free, kind=K.JOB_COMPLETED, message="other", url="/dashboard/")
        self.client.force_login(self.w.owner)
        self.assertEqual(self.client.post("/api/notifications/read-all/").data["updated"], 3)
        self.assertEqual(self.client.get("/api/notifications/unread/").data["count"], 0)
        self.assertEqual(Notification.objects.filter(user=self.w.free, read_at__isnull=True).count(), 1)

    def test_pagination_newest_first_and_unread_filter(self):
        for i in range(25):
            services.notify(user=self.w.owner, kind=K.JOB_COMPLETED, message=f"n{i}", url="/dashboard/")
        self.client.force_login(self.w.owner)
        first = self.client.get("/api/notifications/").data
        self.assertEqual((first["count"], len(first["results"])), (25, 20))
        self.assertEqual(first["results"][0]["message"], "n24")
        self.assertEqual(len(self.client.get("/api/notifications/?page=2").data["results"]), 5)
        self.client.post(f"/api/notifications/{first['results'][0]['id']}/read/")
        self.assertEqual(self.client.get("/api/notifications/?unread=1").data["count"], 24)

    def test_email_setting(self):
        self.client.force_login(self.w.owner)
        url = "/api/notifications/settings/"
        self.assertTrue(self.client.get(url).data["email_enabled"])
        self.assertEqual(self.client.patch(url, {"email_enabled": False}, format="json").status_code, 200)
        self.assertFalse(self.client.get(url).data["email_enabled"])
        self.assertEqual(self.client.patch(url, {"email_enabled": "maybe"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {}, format="json").status_code, 400)

    def test_message_notifications_collapse_and_clear_when_opened(self):
        self.propose(self.w.free)  # leaves the freelancer logged in
        conv = self.client.post("/api/conversations/", {"job_id": self.w.job.id}, format="json").data["id"]
        url = f"/api/conversations/{conv}/messages/"
        for text in ("one", "two", "three"):
            self.assertEqual(self.client.post(url, {"body": text}, format="json").status_code, 201)
        notes = Notification.objects.filter(user=self.w.owner, kind="new_message")
        self.assertEqual(notes.count(), 1)
        self.assertEqual(notes.first().url, f"/messages/?c={conv}")
        self.client.force_login(self.w.owner)
        self.assertEqual(self.client.get("/api/notifications/unread/").data["count"], 2)  # proposal + message
        self.client.get(url)  # opening the chat reads it
        self.assertEqual(self.client.get("/api/notifications/unread/").data["count"], 1)


class NotificationEmailTests(Base):
    def propose_and_flush(self, user=None):
        # Emails go out after the database commit, which tests have to trigger explicitly
        self.client.force_login(user or self.w.free)
        body = {"bid_amount": "450.00", "delivery_days": 14, "cover_letter": COVER}
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(f"/api/jobs/{self.w.job.id}/proposals/", body, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_verified_user_gets_an_email(self):
        self.propose_and_flush()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["owner@example.com"])
        self.assertIn("Free sent a proposal", msg.subject)
        self.assertIn("/dashboard/", msg.body)
        self.assertIn("/notifications/", msg.body)

    def test_unverified_address_gets_no_email(self):
        User.objects.filter(pk=self.w.owner.pk).update(email_verified=False)
        self.propose_and_flush()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notification.objects.filter(user=self.w.owner).count(), 1)  # the bell still works

    def test_switched_off_gets_no_email(self):
        NotificationPreference.objects.create(user=self.w.owner, email_enabled=False)
        self.propose_and_flush()
        self.assertEqual(len(mail.outbox), 0)

    def test_message_burst_sends_one_email(self):
        self.propose_and_flush()
        mail.outbox.clear()
        conv = self.client.post("/api/conversations/", {"job_id": self.w.job.id}, format="json").data["id"]
        url = f"/api/conversations/{conv}/messages/"
        for text in ("one", "two", "three"):
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.client.post(url, {"body": text}, format="json").status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("New message from Free", mail.outbox[0].subject)
        self.assertNotIn("one", mail.outbox[0].body.split("Open it here")[0].replace("New message", ""))

    def test_hourly_email_cap(self):
        for i in range(12):
            with self.captureOnCommitCallbacks(execute=True):
                services.notify(user=self.w.owner, kind=K.JOB_COMPLETED, message=f"n{i}", url="/dashboard/")
        self.assertEqual(len(mail.outbox), services.EMAILS_PER_HOUR)


class NotificationSocketTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.w = build_world()

    def comm(self, user):
        c = WebsocketCommunicator(NotificationConsumer.as_asgi(), "/ws/notifications/")
        c.scope["user"] = user
        return c

    async def test_logged_in_user_can_connect(self):
        c = self.comm(self.w.owner)
        connected, _ = await c.connect()
        self.assertTrue(connected)
        await c.disconnect()

    async def test_anonymous_is_rejected(self):
        c = self.comm(AnonymousUser())
        connected, _ = await c.connect()
        self.assertFalse(connected)

    async def test_new_notification_is_pushed_live(self):
        c = self.comm(self.w.owner)
        await c.connect()
        await sync_to_async(services.notify)(
            user=self.w.owner, kind=K.JOB_COMPLETED, message="Hello there", url="/dashboard/")
        data = await c.receive_json_from(timeout=3)
        self.assertEqual(data["message"], "Hello there")
        self.assertEqual(data["unread"], 1)
        await c.disconnect()