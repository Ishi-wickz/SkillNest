from rest_framework.permissions import BasePermission

from apps.accounts.permissions import email_ok


class IsClient(BasePermission):
    """Logged in, role == client, and a verified email for anything that changes data."""
    def has_permission(self, request, view):
        u = request.user
        return bool(u.is_authenticated and u.role == "client" and email_ok(request))


class IsFreelancer(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u.is_authenticated and u.role == "freelancer" and email_ok(request))


class IsJobOwner(BasePermission):
    """Object-level check: only the client who posted the job."""
    def has_object_permission(self, request, view, obj):
        return obj.client_id == request.user.id