from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import User


class AuthApiTests(APITestCase):
    def setUp(self):
        cache.clear()  # reset the throttle counters between tests
        self.payload = {
            "email": "Client@Example.com",
            "password": "Sturdy-Pass-4821",
            "full_name": "Test Client",
            "role": "client",
        }

    def signup(self, **overrides):
        return self.client.post("/api/auth/signup/", {**self.payload, **overrides}, format="json")

    def test_signup_creates_user_and_profile(self):
        resp = self.signup()
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(email="client@example.com")  # stored lowercase
        self.assertEqual(user.role, "client")
        self.assertEqual(user.profile.full_name, "Test Client")
        self.assertNotIn("password", resp.data)

    def test_cannot_sign_up_as_admin(self):
        resp = self.signup(role="admin")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_duplicate_email_rejected_case_insensitive(self):
        self.signup()
        resp = self.signup(email="CLIENT@example.com")
        self.assertEqual(resp.status_code, 400)

    def test_weak_password_rejected(self):
        resp = self.signup(password="12345")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_login_success_and_me(self):
        User.objects.create_user(email="f@example.com", password="Sturdy-Pass-4821", role="freelancer")
        resp = self.client.post(
            "/api/auth/login/", {"email": "F@Example.com", "password": "Sturdy-Pass-4821"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        me = self.client.get("/api/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["role"], "freelancer")

    def test_login_wrong_password_and_unknown_email_look_the_same(self):
        User.objects.create_user(email="f@example.com", password="Sturdy-Pass-4821", role="freelancer")
        wrong = self.client.post("/api/auth/login/", {"email": "f@example.com", "password": "nope"}, format="json")
        unknown = self.client.post("/api/auth/login/", {"email": "x@example.com", "password": "nope"}, format="json")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.data, unknown.data)

    def test_me_requires_login(self):
        # DRF answers 403 (not 401) when session authentication is used
        self.assertEqual(self.client.get("/api/me/").status_code, 403)

    def test_logout_ends_session(self):
        self.signup()
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/me/").status_code, 403)

    def test_login_is_throttled(self):
        body = {"email": "x@example.com", "password": "nope"}
        for _ in range(10):
            self.client.post("/api/auth/login/", body, format="json")
        self.assertEqual(self.client.post("/api/auth/login/", body, format="json").status_code, 429)