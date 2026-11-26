"""Persist a notification and push it to the user's WebSocket group after commit."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from .models import Notification

log = logging.getLogger(__name__)


def user_group(user_id) -> str:
    return f"user_{user_id}"


def push(user_id, event: dict):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(user_group(user_id), event)
    except Exception:  # noqa: BLE001 - realtime is best-effort; the row is the source of truth
        log.exception("Realtime push failed for user %s", user_id)


def notify(user, verb, title, body="", url="") -> Notification:
    n = Notification.objects.create(user=user, verb=verb, title=title, body=body, url=url)
    payload = n.as_dict()
    transaction.on_commit(lambda: push(user.pk, {"type": "notify", "notification": payload}))
    return n
