from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Conversation(models.Model):
    """One chat per (job, freelancer). The client is always the job's owner."""
    job = models.ForeignKey("marketplace.Job", on_delete=models.CASCADE, related_name="conversations")
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="client_conversations")
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="freelancer_conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now)  # bumped on every message, sorts the inbox

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "freelancer"], name="one_conversation_per_job_freelancer"),
            models.CheckConstraint(condition=~Q(client=F("freelancer")), name="no_self_conversation"),
        ]
        indexes = [
            models.Index(fields=["client", "-updated_at"], name="conv_client_idx"),
            models.Index(fields=["freelancer", "-updated_at"], name="conv_freelancer_idx"),
        ]


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)  # when the other person opened it

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["conversation", "id"], name="msg_conv_id_idx")]