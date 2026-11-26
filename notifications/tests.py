from datetime import timedelta

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils import timezone

from accounts.tokens import RefreshToken
from alcove.asgi import application
from notifications.services import notify

pytestmark = pytest.mark.django_db(transaction=True)


@database_sync_to_async
def _headers(user):
    token = str(RefreshToken.for_user(user).access_token)  # writes an OutstandingToken row
    return [(b"cookie", f"alcove_access={token}".encode()), (b"origin", b"http://localhost")]


async def test_anonymous_socket_rejected():
    comm = WebsocketCommunicator(application, "/ws/notifications/", headers=[(b"origin", b"http://localhost")])
    connected, _ = await comm.connect()
    assert not connected


async def test_notification_pushed_live(renter):
    comm = WebsocketCommunicator(application, "/ws/notifications/", headers=await _headers(renter))
    connected, _ = await comm.connect()
    assert connected
    assert (await comm.receive_json_from())["type"] == "unread"
    await database_sync_to_async(notify)(renter, "test", "Hello", "World")
    msg = await comm.receive_json_from(timeout=3)
    assert msg["type"] == "notification" and msg["notification"]["title"] == "Hello"
    await comm.disconnect()


async def test_owner_sees_guest_position(owner, renter, room):
    from bookings.models import Booking

    today = timezone.localdate()
    b = await database_sync_to_async(Booking.objects.create)(
        renter=renter, property=room.property, room=room, check_in=today, check_out=today + timedelta(days=1),
        nightly_rate=2000, subtotal=2000, taxes=240, total=2240, status="CONFIRMED", share_location=True)
    owner_ws = WebsocketCommunicator(application, "/ws/location/", headers=await _headers(owner))
    renter_ws = WebsocketCommunicator(application, "/ws/location/", headers=await _headers(renter))
    assert (await owner_ws.connect())[0] and (await renter_ws.connect())[0]
    await owner_ws.send_json_to({"action": "watch_booking", "reference": b.reference})
    assert (await owner_ws.receive_json_from())["type"] == "watching"
    await renter_ws.send_json_to({"action": "position", "lat": 12.98, "lng": 77.64})
    nearby = await renter_ws.receive_json_from(timeout=3)
    assert nearby["type"] == "nearby" and nearby["results"][0]["name"] == "Lakeview Rooms"
    pos = await owner_ws.receive_json_from(timeout=3)
    assert pos["type"] == "guest_position" and 0.5 < pos["distance_km"] < 1.5
    await owner_ws.disconnect(); await renter_ws.disconnect()


async def test_stranger_cannot_watch_booking(renter, owner, room):
    ws = WebsocketCommunicator(application, "/ws/location/", headers=await _headers(renter))
    await ws.connect()
    await ws.send_json_to({"action": "watch_booking", "reference": "ALCNOPE"})
    assert (await ws.receive_json_from())["type"] == "error"
    await ws.disconnect()
