from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "message", "url", "read", "created_at"]
        read_only_fields = fields

    def get_read(self, note):
        return note.read_at is not None


class SettingsSerializer(serializers.Serializer):
    email_enabled = serializers.BooleanField()