from rest_framework import serializers

from apps.marketplace.serializers import full_name

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(read_only=True)  # ids only, never emails

    class Meta:
        model = Message
        fields = ["id", "sender_id", "body", "created_at", "read_at"]
        read_only_fields = fields


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000)  # blank or whitespace-only is rejected


class StartConversationSerializer(serializers.Serializer):
    job_id = serializers.IntegerField(min_value=1)
    freelancer_id = serializers.IntegerField(min_value=1, required=False)


class ConversationSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    other = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "job", "job_title", "other", "last_message", "unread_count", "updated_at"]
        read_only_fields = fields

    def get_other(self, conv):
        me = self.context["request"].user
        other = conv.freelancer if me.id == conv.client_id else conv.client
        return {"id": other.id, "full_name": full_name(other)}

    def get_last_message(self, conv):
        if conv.last_body is None:
            return None
        return {"body": conv.last_body, "created_at": conv.last_at, "sender_id": conv.last_sender_id}