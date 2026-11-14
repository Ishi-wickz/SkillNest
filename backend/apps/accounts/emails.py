import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User

log = logging.getLogger(__name__)

VERIFY_SALT = "skillnest.email-verify"
VERIFY_MAX_AGE = 3 * 24 * 60 * 60  # the verification link works for 3 days


def _link(path, **params):
    # SITE_URL comes from settings, never from the request, so a forged Host header can't poison it
    return f"{settings.SITE_URL.rstrip('/')}{path}?{urlencode(params)}"


def _greeting(user):
    profile = getattr(user, "profile", None)  # superusers made in the terminal have no profile
    return f"Hi {profile.full_name}," if profile else "Hi,"


def _allowed(kind, email, seconds=60):
    """One email of each kind per address per minute: stops double clicks and inbox flooding."""
    return cache.add(f"mail:{kind}:{email}", 1, timeout=seconds)


def _send(subject, body, to):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to])
    except Exception:
        # A mail outage must never break signup, or reveal whether an account exists
        log.exception("Could not send the %r email", subject)


# ---------- Email verification: a signed, expiring token that also carries the address ----------
def send_verification_email(user):
    if user.email_verified or not _allowed("verify", user.email):
        return
    token = signing.dumps({"u": user.pk, "e": user.email}, salt=VERIFY_SALT)
    url = _link("/verify-email/", token=token)
    _send(
        "Verify your SkillNest email",
        f"{_greeting(user)}\n\n"
        f"Welcome to SkillNest! Please confirm your email address by opening this link:\n\n{url}\n\n"
        "The link works for 3 days. If you didn't create an account, you can ignore this email.\n\n"
        "The SkillNest team\n",
        user.email,
    )


def user_from_verify_token(token):
    try:
        data = signing.loads(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)  # bad or expired -> BadSignature
    except signing.BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    # Matching on the email too means the link dies if the address is ever changed
    return User.objects.filter(pk=data.get("u"), email=data.get("e"), is_active=True).first()


# ---------- Password reset: Django's token, which stops working once the password changes ----------
def send_password_reset(email):
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None or not _allowed("reset", user.email):
        return  # say nothing: the caller answers the same way either way
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = _link("/reset-password/", uid=uid, token=token)
    _send(
        "Reset your SkillNest password",
        f"{_greeting(user)}\n\n"
        f"We received a request to reset your SkillNest password. Open this link to choose a new one:\n\n{url}\n\n"
        "The link works for 1 hour and can be used once. If you didn't ask for this, ignore this "
        "email and your password stays the same.\n\n"
        "The SkillNest team\n",
        user.email,
    )


def user_from_reset_link(uid, token):
    try:
        pk = urlsafe_base64_decode(uid).decode()
        user = User.objects.get(pk=pk, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    return user if default_token_generator.check_token(user, token) else None