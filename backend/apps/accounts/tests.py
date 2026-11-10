from django.core.cache import cache

from rest_framework.test import APITestCase
from apps.marketplace.models import Skill
from .models import Profile, User


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
        
        
        
PW = "Sturdy-Pass-4821"


def make(email, role, name, rate=None):
    user = User.objects.create_user(email=email, password=PW, role=role)
    return Profile.objects.create(user=user, full_name=name, hourly_rate=rate)      
    

class TalentApiTests(APITestCase):
    def setUp(self):
        self.python = Skill.objects.create(name="Python", slug="python")
        self.ann = make("ann@example.com", "freelancer", "Ann Dev", 30)
        self.ann.skills.add(self.python)
        self.bob = make("bob@example.com", "freelancer", "Bob Writer", 10)
        self.client_profile = make("c@example.com", "client", "Cathy Client")

    def names(self, query=""):
        resp = self.client.get("/api/talent/" + query)
        self.assertEqual(resp.status_code, 200)
        return sorted(t["full_name"] for t in resp.data["results"])

    def test_public_and_freelancers_only(self):
        self.assertEqual(self.names(), ["Ann Dev", "Bob Writer"])

    def test_no_email_exposed(self):
        resp = self.client.get("/api/talent/")
        self.assertNotIn("example.com", str(resp.data))

    def test_filters(self):
        self.assertEqual(self.names("?skill=python"), ["Ann Dev"])
        self.assertEqual(self.names("?q=writer"), ["Bob Writer"])
        self.assertEqual(self.names("?q=python"), ["Ann Dev"])
        self.assertEqual(self.names("?min=20"), ["Ann Dev"])
        self.assertEqual(self.names("?max=20"), ["Bob Writer"])
        self.assertEqual(self.client.get("/api/talent/?min=abc").status_code, 400)

    def test_detail_and_client_profile_hidden(self):
        self.assertEqual(self.client.get(f"/api/talent/{self.ann.id}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/talent/{self.client_profile.id}/").status_code, 404)
        
        
        
class ProfileApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.python = Skill.objects.create(name="Python", slug="python")
        self.free = User.objects.create_user(email="f@example.com", password="Sturdy-Pass-4821", role="freelancer")
        Profile.objects.create(user=self.free, full_name="Free Lancer")
        self.cl = User.objects.create_user(email="c@example.com", password="Sturdy-Pass-4821", role="client")
        Profile.objects.create(user=self.cl, full_name="Cli Ent")

    def test_requires_login(self):
        self.assertEqual(self.client.get("/api/profile/").status_code, 403)

    def test_freelancer_can_update(self):
        self.client.force_login(self.free)
        resp = self.client.patch("/api/profile/", {"bio": "Hi", "hourly_rate": "25.00",
                                                  "skill_ids": [self.python.id]}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.free.profile.refresh_from_db()
        self.assertEqual(self.free.profile.bio, "Hi")
        self.assertEqual(list(self.free.profile.skills.all()), [self.python])

    def test_client_cannot_set_rate_or_skills(self):
        self.client.force_login(self.cl)
        self.assertEqual(self.client.patch("/api/profile/", {"hourly_rate": "10"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch("/api/profile/", {"skill_ids": [self.python.id]}, format="json").status_code, 400)

    def test_negative_rate_rejected(self):
        self.client.force_login(self.free)
        self.assertEqual(self.client.patch("/api/profile/", {"hourly_rate": "-5"}, format="json").status_code, 400)
