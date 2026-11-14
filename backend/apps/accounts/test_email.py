import re
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.marketplace.models import Category

from .models import User

PW = "Sturdy-Pass-4821"
NEW_PW = "Another-Pass-9376"
SIGNUP = {"email": "New@Example.com", "password": PW, "full_name": "New Person", "role": "client"}


def link_params(message):
    """The query parameters of the first link in an email body."""
    url = re.search(r"https?://\S+", message.body).group(0)
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


class EmailVerificationTests(APITestCase):
    def setUp(self):
        cache.clear()

    def signup(self):
        resp = self.client.post("/api/auth/signup/", SIGNUP, format="json")
        self.assertEqual(resp.status_code, 201)
        return resp

    def confirm(self, token):
        return self.client.post("/api/auth/verify-email/confirm/", {"token": token}, format="json")

    def test_signup_sends_email_and_starts_unverified(self):
        resp = self.signup()
        self.assertFalse(resp.data["email_verified"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertIn("token=", mail.outbox[0].body)

    def test_link_verifies_the_account(self):
        self.signup()
        token = link_params(mail.outbox[0])["token"]
        self.assertEqual(self.confirm(token).status_code, 200)
        self.assertTrue(User.objects.get(email="new@example.com").email_verified)
        self.assertEqual(self.confirm(token).status_code, 200)  # clicking twice is harmless

    def test_garbage_and_tampered_tokens_rejected(self):
        self.signup()
        token = link_params(mail.outbox[0])["token"]
        self.assertEqual(self.confirm("garbage").status_code, 400)
        self.assertEqual(self.confirm(token + "x").status_code, 400)
        self.assertFalse(User.objects.get(email="new@example.com").email_verified)

    def test_token_dies_if_the_email_changes(self):
        self.signup()
        token = link_params(mail.outbox[0])["token"]
        User.objects.filter(email="new@example.com").update(email="changed@example.com")
        self.assertEqual(self.confirm(token).status_code, 400)

    def test_resend_needs_login_and_has_a_cooldown(self):
        user = User.objects.create_user(email="a@example.com", password=PW, role="client")
        url = "/api/auth/verify-email/send/"
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(user)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(len(mail.outbox), 1)  # a second click within a minute sends nothing

    @override_settings(REQUIRE_VERIFIED_EMAIL=True)
    def test_unverified_cannot_post_jobs_until_verified(self):
        user = User.objects.create_user(email="c@example.com", password=PW, role="client")
        cat = Category.objects.create(name="Web", slug="web")
        body = {"title": "A job", "description": "Details here", "budget_type": "fixed",
                "budget_amount": "100.00", "currency": "USD", "category_id": cat.id}
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/jobs/").status_code, 200)  # reading is always fine
        resp = self.client.post("/api/jobs/", body, format="json")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("verify", str(resp.data["detail"]).lower())
        user.email_verified = True
        user.save()
        self.assertEqual(self.client.post("/api/jobs/", body, format="json").status_code, 201)

    @override_settings(REQUIRE_VERIFIED_EMAIL=True)
    def test_unverified_cannot_open_chats(self):
        user = User.objects.create_user(email="f@example.com", password=PW, role="freelancer")
        self.client.force_login(user)
        resp = self.client.post("/api/conversations/", {"job_id": 1}, format="json")
        self.assertEqual(resp.status_code, 403)


class PasswordResetTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="a@example.com", password=PW, role="client")

    def request_reset(self, email="a@example.com"):
        return self.client.post("/api/auth/password-reset/", {"email": email}, format="json")

    def confirm(self, params, password=NEW_PW):
        return self.client.post("/api/auth/password-reset/confirm/",
                                {**params, "password": password}, format="json")

    def login(self, password):
        return self.client.post("/api/auth/login/",
                                {"email": "a@example.com", "password": password}, format="json")

    def test_known_and_unknown_emails_look_identical(self):
        known = self.request_reset()
        unknown = self.request_reset("nobody@example.com")
        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["a@example.com"])

    def test_full_flow_changes_the_password(self):
        self.request_reset("A@EXAMPLE.COM")  # case-insensitive
        params = link_params(mail.outbox[0])
        self.assertEqual(set(params), {"uid", "token"})
        self.assertEqual(self.confirm(params).status_code, 200)
        self.assertEqual(self.login(PW).status_code, 401)
        self.assertEqual(self.login(NEW_PW).status_code, 200)

    def test_link_works_only_once(self):
        self.request_reset()
        params = link_params(mail.outbox[0])
        self.assertEqual(self.confirm(params).status_code, 200)
        self.assertEqual(self.confirm(params, "Third-Pass-5512").status_code, 400)
        self.assertEqual(self.login(NEW_PW).status_code, 200)

    def test_weak_password_is_refused_and_the_link_stays_valid(self):
        self.request_reset()
        params = link_params(mail.outbox[0])
        self.assertEqual(self.confirm(params, "12345").status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PW))  # unchanged, checked without logging in
        self.assertEqual(self.confirm(params).status_code, 200)  # the same link still works

    def test_bad_links_are_rejected(self):
        self.request_reset()
        params = link_params(mail.outbox[0])
        self.assertEqual(self.confirm({"uid": "zzzz", "token": params["token"]}).status_code, 400)
        self.assertEqual(self.confirm({"uid": "OTk5OTk5", "token": params["token"]}).status_code, 400)  # no such user
        self.assertEqual(self.confirm({"uid": params["uid"], "token": "bad-token"}).status_code, 400)
        self.assertEqual(self.confirm({"uid": params["uid"], "token": params["token"] + "x"}).status_code, 400)

    def test_reset_also_verifies_the_email(self):
        self.assertFalse(self.user.email_verified)
        self.request_reset()
        self.confirm(link_params(mail.outbox[0]))
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_cooldown_sends_only_one_email_per_minute(self):
        self.request_reset()
        self.request_reset()
        self.assertEqual(len(mail.outbox), 1)

    def test_inactive_accounts_get_nothing(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.request_reset().status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_requests_are_throttled(self):
        for _ in range(5):
            self.assertEqual(self.request_reset().status_code, 200)
        self.assertEqual(self.request_reset().status_code, 429)