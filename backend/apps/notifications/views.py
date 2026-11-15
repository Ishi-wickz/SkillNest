from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Notification
from .serializers import NotificationSerializer, SettingsSerializer


class NotificationPagination(PageNumberPagination):
    page_size = 20


class NotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)  # only ever your own
        if self.request.query_params.get("unread") == "1":
            qs = qs.filter(read_at__isnull=True)
        return qs.order_by("-id")


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"count": services.unread_count(request.user.id)})


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        note = get_object_or_404(Notification, pk=pk, user=request.user)  # someone else's id gives 404
        Notification.objects.filter(pk=note.pk, read_at__isnull=True).update(read_at=timezone.now())
        note.refresh_from_db()
        return Response(NotificationSerializer(note).data)


class MarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(user=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response({"updated": updated})


class SettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"email_enabled": services.email_enabled(request.user)})

    def patch(self, request):
        data = SettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.set_email_enabled(request.user, data.validated_data["email_enabled"])
        return Response({"email_enabled": data.validated_data["email_enabled"]})