from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Notification(models.Model):
    class Kind(models.TextChoices):
        PROPOSAL_RECEIVED = "proposal_received", "Proposal received"
        PROPOSAL_ACCEPTED = "proposal_accepted", "Proposal accepted"
        PROPOSAL_REJECTED = "proposal_rejected", "Proposal rejected"
        PROPOSAL_WITHDRAWN = "proposal_withdrawn", "Proposal withdrawn"
        JOB_COMPLETED = "job_completed", "Job completed"
        REVIEW_RECEIVED = "review_received", "Review received"
        NEW_MESSAGE = "new_message", "New message"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    message = models.CharField(max_length=200)   # plain text, never HTML
    url = models.CharField(max_length=200)       # an internal path such as /dashboard/
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["user", "-id"], name="notif_user_idx"),
            models.Index(fields=["user", "read_at"], name="notif_unread_idx"),
        ]


class NotificationPreference(models.Model):
    """Created only when someone changes a setting. No row means the defaults apply."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="notification_pref")
    email_enabled = models.BooleanField(default=True)