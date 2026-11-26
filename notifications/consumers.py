from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Notification
from .services import user_group


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4401)
            return
        self.group = user_group(user.pk)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json({"type": "unread", "count": await self._unread()})

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("action") == "mark_read":
            await self._mark_read(content.get("id"))
            await self.send_json({"type": "unread", "count": await self._unread()})

    async def notify(self, event):
        await self.send_json({"type": "notification", "notification": event["notification"]})

    @database_sync_to_async
    def _unread(self):
        return Notification.objects.filter(user=self.scope["user"], is_read=False).count()

    @database_sync_to_async
    def _mark_read(self, nid):
        qs = Notification.objects.filter(user=self.scope["user"], is_read=False)
        if nid != "all":
            qs = qs.filter(pk=nid)
        qs.update(is_read=True)
