from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db.models import Q

from .models import Conversation


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Receive-only doorbell. Sending messages goes through the REST API."""

    async def connect(self):
        user = self.scope["user"]  # filled in from the session cookie
        self.pk = self.scope["url_route"]["kwargs"]["pk"]
        if not user.is_authenticated or not await self.is_participant(user.id):
            await self.close()  # closing before accept() rejects the handshake
            return
        self.group = f"chat_{self.pk}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        pass  # anything a browser pushes is ignored on purpose

    async def chat_message(self, event):
        await self.send_json(event["message"])

    @database_sync_to_async
    def is_participant(self, user_id):
        return (
            Conversation.objects.filter(pk=self.pk)
            .filter(Q(client_id=user_id) | Q(freelancer_id=user_id))
            .exists()
        )