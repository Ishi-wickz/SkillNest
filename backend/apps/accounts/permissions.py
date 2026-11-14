from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

MESSAGE = "Please verify your email address first. Check your inbox for the link."


def email_ok(request):
    """Reading is always allowed. Changing things needs a verified email."""
    if request.method in SAFE_METHODS or not settings.REQUIRE_VERIFIED_EMAIL:
        return True
    if getattr(request.user, "email_verified", False):
        return True
    raise PermissionDenied(MESSAGE)  # the front end shows this text to the user


class IsVerified(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and email_ok(request))