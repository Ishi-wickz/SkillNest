from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "kind", "message", "read_at", "created_at"]
    list_filter = ["kind"]
    list_select_related = ["user"]