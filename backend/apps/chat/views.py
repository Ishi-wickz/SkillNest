from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerified

from . import services
from .serializers import (ConversationSerializer, MessageCreateSerializer, MessageSerializer,
                          StartConversationSerializer)


class InboxPagination(PageNumberPagination):
    page_size = 50


class ConversationListCreateView(generics.ListAPIView):
    """GET = my inbox. POST = open (or find) the chat for a job."""
    serializer_class = ConversationSerializer
    pagination_class = InboxPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsVerified()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return services.inbox(self.request.user)

    def post(self, request):
        data = StartConversationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        conv = services.get_or_create_conversation(
            user=request.user,
            job_id=data.validated_data["job_id"],
            freelancer_id=data.validated_data.get("freelancer_id"),
        )
        return Response({"id": conv.id})


class MessagesView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsVerified()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "messages"  # 30 per minute, set in settings.py
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get(self, request, pk):
        conv = services.conversation_for_user(request.user, pk)
        qs = conv.messages.all()
        after = request.query_params.get("after")
        if after:
            try:
                after_id = int(after)
            except ValueError:
                raise ValidationError({"after": "Must be a number."})
            messages = list(qs.filter(id__gt=after_id)[:100])
        else:
            messages = list(reversed(list(qs.order_by("-id")[:50])))
        services.mark_read(conv, request.user)
        return Response({"results": MessageSerializer(messages, many=True).data})

    def post(self, request, pk):
        conv = services.conversation_for_user(request.user, pk)
        data = MessageCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        message = services.send_message(
            conversation=conv, sender=request.user, body=data.validated_data["body"]
        )
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"count": services.unread_count(request.user)})