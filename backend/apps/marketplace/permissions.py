from rest_framework.permissions import BasePermission


class IsClient(BasePermission):
    """Logged in and role == client."""
    def has_permission(self, request, view):
        u = request.user
        return bool(u.is_authenticated and u.role == "client")


class IsFreelancer(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u.is_authenticated and u.role == "freelancer")


class IsJobOwner(BasePermission):
    """Object-level check: only the client who posted the job."""
    def has_object_permission(self, request, view, obj):
        return obj.client_id == request.user.id