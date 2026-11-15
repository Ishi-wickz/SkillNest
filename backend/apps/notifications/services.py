import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Notification, NotificationPreference

log = logging.getLogger(__name__)

EMAILS_PER_HOUR = 10  # per user, so a burst of activity can't flood an inbox


def who(user):
    """A display name. Superusers made in the terminal have no profile."""
    profile = getattr(user, "profile", None)
    return profile.full_name if profile else "Someone"


def short(text, limit=60):
    text = " ".join(str(text).split())  # collapses newlines, so subjects stay on one line
    return text if len(text) <= limit else text[: limit - 3] + "..."


def email_enabled(user):
    pref = NotificationPreference.objects.filter(user=user).first()
    return True if pref is None else pref.email_enabled


def set_email_enabled(user, value):
    NotificationPreference.objects.update_or_create(user=user, defaults={"email_enabled": value})


def unread_count(user_id):
    return Notification.objects.filter(user_id=user_id, read_at__isnull=True).count()


def mark_read_for_url(user, url):
    """Opening a conversation clears its message notification."""
    return Notification.objects.filter(user=user, url=url, read_at__isnull=True).update(read_at=timezone.now())


def notify(*, user, kind, message, url, collapse=False, email=True):
    """
    Create a notification. Call it inside the same transaction as the event.
    It never raises: a notification problem must not undo a proposal or a message.
    collapse=True replaces an older unread notification for the same thing and skips the email.
    """
    message = short(message, 200)
    try:
        with transaction.atomic():  # a savepoint: if this fails, the outer transaction survives
            replaced = False
            if collapse:
                old = Notification.objects.filter(user=user, kind=kind, url=url, read_at__isnull=True)
                replaced = old.exists()
                old.delete()
            note = Notification.objects.create(user=user, kind=kind, message=message, url=url)
    except Exception:
        log.exception("Could not create a %s notification", kind)
        return None
    send_email = email and not replaced
    # Only after the commit, so nobody is told about something that was rolled back
    transaction.on_commit(lambda: _after_commit(note, send_email))
    return note


def _after_commit(note, send_email):
    _ring_doorbell(note)
    if send_email:
        _send_email(note)


def _ring_doorbell(note):
    try:
        layer = get_channel_layer()
        if layer is None:
            return
        payload = {
            "id": note.id, "kind": note.kind, "message": note.message, "url": note.url,
            "unread": unread_count(note.user_id),
        }
        async_to_sync(layer.group_send)(
            f"notify_{note.user_id}", {"type": "notification.new", "payload": payload}
        )
    except Exception:  # e.g. Redis is down: the 30-second refresh still shows it
        log.exception("Could not broadcast notification %s", note.pk)


def _under_email_cap(user_id):
    key = f"notifymail:{user_id}"
    cache.add(key, 0, timeout=3600)
    try:
        return cache.incr(key) <= EMAILS_PER_HOUR
    except ValueError:  # the key expired between the two calls
        return True


def _send_email(note):
    try:
        user = note.user
        # Only to addresses the person has proven they own, and only if they haven't opted out
        if not (user.is_active and user.email_verified and email_enabled(user)):
            return
        if not _under_email_cap(user.pk):
            return
        base = settings.SITE_URL.rstrip("/")
        profile = getattr(user, "profile", None)
        greeting = f"Hi {profile.full_name}," if profile else "Hi,"
        send_mail(
            f"SkillNest: {note.message}"[:150],
            f"{greeting}\n\n{note.message}\n\nOpen it here:\n{base}{note.url}\n\n"
            "You receive this because of activity on your SkillNest account. "
            f"To stop these emails, switch them off here:\n{base}/notifications/\n\n"
            "The SkillNest team\n",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
    except Exception:
        log.exception("Could not email notification %s", note.pk)