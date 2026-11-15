import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.marketplace.models import Job, Proposal
from apps.notifications import services as notifications
from apps.notifications.models import Notification

from .models import Conversation, Message

log = logging.getLogger(__name__)


def _mine(user):
    return Q(client=user) | Q(freelancer=user)


def _chat_url(conversation):
    return f"/messages/?c={conversation.pk}"


def conversation_for_user(user, pk):
    conv = Conversation.objects.filter(pk=pk).filter(_mine(user)).first()
    if conv is None:
        raise NotFound("Conversation not found.")
    return conv


def get_or_create_conversation(*, user, job_id, freelancer_id=None):
    job = Job.objects.select_related("client").filter(pk=job_id).first()
    if job is None:
        raise NotFound("Job not found.")

    if user.role == User.Role.FREELANCER:
        freelancer = user
    elif user.role == User.Role.CLIENT:
        if job.client_id != user.id:
            raise NotFound("Job not found.")
        if not freelancer_id:
            raise ValidationError({"freelancer_id": "This field is required."})
        freelancer = User.objects.filter(
            pk=freelancer_id, role=User.Role.FREELANCER, is_active=True
        ).first()
        if freelancer is None:
            raise NotFound("Freelancer not found.")
    else:
        raise PermissionDenied("Only clients and freelancers can send messages.")

    if not Proposal.objects.filter(job=job, freelancer=freelancer).exists():
        raise ValidationError({"detail": "You can message once the freelancer has sent a proposal for this job."})

    conv, _ = Conversation.objects.get_or_create(
        job=job, freelancer=freelancer, defaults={"client": job.client}
    )
    return conv


def inbox(user):
    last = Message.objects.filter(conversation=OuterRef("pk")).order_by("-id")
    unread = (
        Message.objects.filter(conversation=OuterRef("pk"), read_at__isnull=True)
        .exclude(sender=user)
        .order_by()
        .values("conversation")
        .annotate(n=Count("id"))
        .values("n")
    )
    return (
        Conversation.objects.filter(_mine(user))
        .select_related("job", "client__profile", "freelancer__profile")
        .annotate(
            unread_count=Coalesce(Subquery(unread), Value(0)),
            last_body=Subquery(last.values("body")[:1]),
            last_at=Subquery(last.values("created_at")[:1]),
            last_sender_id=Subquery(last.values("sender_id")[:1]),
        )
        .order_by("-updated_at", "-id")
    )


def unread_count(user):
    return (
        Message.objects.filter(read_at__isnull=True)
        .filter(Q(conversation__client=user) | Q(conversation__freelancer=user))
        .exclude(sender=user)
        .count()
    )


def mark_read(conversation, user):
    conversation.messages.filter(read_at__isnull=True).exclude(sender=user).update(read_at=timezone.now())
    # Opening the chat also clears its bell notification
    notifications.mark_read_for_url(user, _chat_url(conversation))


def _ring_doorbell(message):
    try:
        from .serializers import MessageSerializer

        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            f"chat_{message.conversation_id}",
            {"type": "chat.message", "message": dict(MessageSerializer(message).data)},
        )
    except Exception:
        log.exception("Could not broadcast message %s", message.pk)


@transaction.atomic
def send_message(*, conversation, sender, body):
    body = body.strip()
    if not body:
        raise ValidationError({"body": "Message cannot be empty."})
    message = Message.objects.create(conversation=conversation, sender=sender, body=body)
    Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())

    recipient = conversation.freelancer if sender.id == conversation.client_id else conversation.client
    # collapse=True: ten messages in a row give one unread notification and one email
    notifications.notify(
        user=recipient, kind=Notification.Kind.NEW_MESSAGE, collapse=True,
        message=f"New message from {notifications.who(sender)}", url=_chat_url(conversation),
    )
    transaction.on_commit(lambda: _ring_doorbell(message))
    return message