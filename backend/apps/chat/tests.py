from decimal import Decimal
from types import SimpleNamespace

from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.core.cache import cache
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from apps.accounts.models import Profile, User
from apps.marketplace.models import Category, Job, Proposal

from . import services
from .consumers import ChatConsumer
from .models import Conversation, Message

PW = "Sturdy-Pass-4821"


def make_user(email, role):
    user = User.objects.create_user(email=email, password=PW, role=role)
    Profile.objects.create(user=user, full_name=email.split("@")[0].title())
    return user


def build_world():
    w = SimpleNamespace()
    w.owner = make_user("owner@example.com", "client")
    w.other_client = make_user("other@example.com", "client")
    w.free = make_user("free@example.com", "freelancer")    # has a proposal
    w.free2 = make_user("free2@example.com", "freelancer")  # never proposed
    cat = Category.objects.create(name="Web", slug="web")
    w.job = Job.objects.create(client=w.owner, category=cat, title="Build API",
                               description="Need a Django API", budget_type="fixed",
                               budget_amount=Decimal("500"), currency="USD")
    Proposal.objects.create(job=w.job, freelancer=w.free, bid_amount=Decimal("450"),
                            delivery_days=14, cover_letter="I can do this job well and on time.")
    return w


class ChatApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.w = build_world()

    def conv(self):
        return Conversation.objects.create(job=self.w.job, client=self.w.owner, freelancer=self.w.free)

    def start(self, user, **body):
        self.client.force_login(user)
        return self.client.post("/api/conversations/", body, format="json")

    def test_anonymous_is_blocked(self):
        conv = self.conv()
        self.assertEqual(self.client.get("/api/conversations/").status_code, 403)
        self.assertEqual(self.client.get("/api/messages/unread/").status_code, 403)
        self.assertEqual(self.client.post(f"/api/conversations/{conv.id}/messages/",
                                          {"body": "hi"}, format="json").status_code, 403)

    def test_freelancer_with_proposal_can_start_and_it_is_idempotent(self):
        r1 = self.start(self.w.free, job_id=self.w.job.id)
        r2 = self.start(self.w.free, job_id=self.w.job.id)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data["id"], r2.data["id"])
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Conversation.objects.get().client, self.w.owner)

    def test_freelancer_without_proposal_cannot_start(self):
        self.assertEqual(self.start(self.w.free2, job_id=self.w.job.id).status_code, 400)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_client_start_rules(self):
        ok = self.start(self.w.owner, job_id=self.w.job.id, freelancer_id=self.w.free.id)
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.start(self.w.owner, job_id=self.w.job.id).status_code, 400)
        self.assertEqual(self.start(self.w.owner, job_id=self.w.job.id,
                                    freelancer_id=self.w.free2.id).status_code, 400)  # never proposed
        self.assertEqual(self.start(self.w.owner, job_id=self.w.job.id,
                                    freelancer_id=self.w.other_client.id).status_code, 404)  # not a freelancer
        self.assertEqual(self.start(self.w.other_client, job_id=self.w.job.id,
                                    freelancer_id=self.w.free.id).status_code, 404)  # not the job owner
        self.assertEqual(self.start(self.w.free, job_id=99999).status_code, 404)

    def test_send_receive_and_read_state(self):
        conv = self.conv()
        url = f"/api/conversations/{conv.id}/messages/"
        self.client.force_login(self.w.free)
        sent = self.client.post(url, {"body": "Hello!"}, format="json")
        self.assertEqual(sent.status_code, 201)
        self.assertEqual(sent.data["sender_id"], self.w.free.id)

        self.client.force_login(self.w.owner)
        self.assertEqual(self.client.get("/api/messages/unread/").data["count"], 1)
        inbox = self.client.get("/api/conversations/").data["results"]
        self.assertEqual(inbox[0]["unread_count"], 1)
        self.assertEqual(inbox[0]["last_message"]["body"], "Hello!")
        self.assertEqual(len(self.client.get(url).data["results"]), 1)
        self.assertEqual(self.client.get("/api/messages/unread/").data["count"], 0)  # opening marks it read

        self.client.force_login(self.w.free)  # your own messages are never "unread" for you
        self.assertEqual(self.client.get("/api/messages/unread/").data["count"], 0)

    def test_after_parameter(self):
        conv = self.conv()
        first = services.send_message(conversation=conv, sender=self.w.free, body="one")
        services.send_message(conversation=conv, sender=self.w.free, body="two")
        self.client.force_login(self.w.owner)
        url = f"/api/conversations/{conv.id}/messages/"
        data = self.client.get(f"{url}?after={first.id}").data["results"]
        self.assertEqual([m["body"] for m in data], ["two"])
        self.assertEqual(self.client.get(f"{url}?after=abc").status_code, 400)

    def test_outsiders_get_404(self):
        conv = self.conv()
        url = f"/api/conversations/{conv.id}/messages/"
        for outsider in (self.w.other_client, self.w.free2):
            self.client.force_login(outsider)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {"body": "hi"}, format="json").status_code, 404)
            self.assertEqual(self.client.get("/api/conversations/").data["results"], [])
        self.assertEqual(Message.objects.count(), 0)

    def test_empty_and_overlong_messages_rejected(self):
        conv = self.conv()
        url = f"/api/conversations/{conv.id}/messages/"
        self.client.force_login(self.w.free)
        for body in ("", "   ", "x" * 2001):
            self.assertEqual(self.client.post(url, {"body": body}, format="json").status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_inbox_never_shows_emails(self):
        conv = self.conv()
        services.send_message(conversation=conv, sender=self.w.free, body="Hi there")
        self.client.force_login(self.w.free)
        data = self.client.get("/api/conversations/").data
        self.assertNotIn("example.com", str(data))
        self.assertEqual(data["results"][0]["other"]["full_name"], "Owner")


class ChatSocketTests(TransactionTestCase):
    def setUp(self):
        self.w = build_world()
        self.conv = Conversation.objects.create(job=self.w.job, client=self.w.owner, freelancer=self.w.free)

    def comm(self, user):
        c = WebsocketCommunicator(ChatConsumer.as_asgi(), f"/ws/chat/{self.conv.id}/")
        c.scope["user"] = user
        c.scope["url_route"] = {"kwargs": {"pk": self.conv.id}}
        return c

    async def test_participant_can_connect(self):
        c = self.comm(self.w.owner)
        connected, _ = await c.connect()
        self.assertTrue(connected)
        await c.disconnect()

    async def test_outsider_is_rejected(self):
        c = self.comm(self.w.other_client)
        connected, _ = await c.connect()
        self.assertFalse(connected)

    async def test_new_message_is_pushed_live(self):
        c = self.comm(self.w.owner)
        await c.connect()
        await sync_to_async(services.send_message)(
            conversation=self.conv, sender=self.w.free, body="Live!")
        data = await c.receive_json_from(timeout=3)
        self.assertEqual(data["body"], "Live!")
        await c.disconnect()