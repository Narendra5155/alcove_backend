"""Live location over WebSockets.

Renter -> {"action": "position", "lat", "lng", "radius_km"}
    <- {"type": "nearby", "results": [...]}       (properties around them, via Redis GEO)
    and, for an arrival-day booking with sharing on, the position is fanned out to `booking_<id>`.

Owner  -> {"action": "watch_booking", "reference": "ALC..."}
    <- {"type": "guest_position", "lat", "lng", "distance_km", "ts"}
"""

import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.utils import timezone

from notifications.services import notify

from . import services

MIN_INTERVAL = 2.0  # seconds between accepted position updates per socket
NEARBY_ALERT_KM = 1.0


def booking_group(booking_id):
    return f"booking_{booking_id}"


class LocationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.last_update = 0.0
        self.watching = set()
        await self.accept()

    async def disconnect(self, code):
        for g in self.watching:
            await self.channel_layer.group_discard(g, self.channel_name)
        if self.user.is_authenticated and getattr(self.user, "role", "") == "RENTER":
            await database_sync_to_async(services.clear_position)(self.user.pk)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action == "position":
            await self._handle_position(content)
        elif action == "watch_booking":
            await self._watch_booking(content.get("reference", ""))

    # ------------------------------------------------------------ renter
    async def _handle_position(self, content):
        now = time.monotonic()
        if now - self.last_update < MIN_INTERVAL:
            return
        self.last_update = now
        try:
            lat, lng = float(content["lat"]), float(content["lng"])
            radius = min(max(float(content.get("radius_km", 10)), 0.5), 50)
        except (KeyError, TypeError, ValueError):
            return await self.send_json(
                {"type": "error", "detail": "Invalid coordinates."}
            )
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return await self.send_json(
                {"type": "error", "detail": "Invalid coordinates."}
            )

        results = await database_sync_to_async(services.nearby_properties)(
            lat, lng, radius
        )
        await self.send_json(
            {"type": "nearby", "results": results, "center": {"lat": lat, "lng": lng}}
        )

        if self.user.is_authenticated and self.user.role == "RENTER":
            await database_sync_to_async(services.update_position)(
                self.user.pk, lat, lng, content.get("accuracy")
            )
            for b in await self._sharing_bookings():
                dist_km = await database_sync_to_async(_distance_km)(b, lat, lng)
                await self.channel_layer.group_send(
                    booking_group(b.pk),
                    {
                        "type": "guest.position",
                        "lat": lat,
                        "lng": lng,
                        "distance_km": dist_km,
                        "ts": time.time(),
                    },
                )
                await database_sync_to_async(_maybe_alert_owner)(b, dist_km)

    @database_sync_to_async
    def _sharing_bookings(self):
        from bookings.models import Booking

        return list(
            Booking.objects.filter(
                renter=self.user,
                status=Booking.Status.CONFIRMED,
                share_location=True,
                check_in=timezone.localdate(),
            ).select_related("property__owner", "renter")
        )

    # ------------------------------------------------------------ owner
    async def _watch_booking(self, reference):
        booking = await self._owned_booking(reference)
        if not booking:
            return await self.send_json(
                {"type": "error", "detail": "Booking not found."}
            )
        group = booking_group(booking.pk)
        await self.channel_layer.group_add(group, self.channel_name)
        self.watching.add(group)
        last = (
            await database_sync_to_async(services.get_position)(booking.renter_id)
            if booking.share_location
            else None
        )
        payload = {
            "type": "watching",
            "reference": reference,
            "sharing": booking.share_location,
            "property": {"lat": booking.property.lat, "lng": booking.property.lng},
        }
        if last:
            payload["last"] = {
                **last,
                "distance_km": await database_sync_to_async(_distance_km)(
                    booking, last["lat"], last["lng"]
                ),
            }
        await self.send_json(payload)

    @database_sync_to_async
    def _owned_booking(self, reference):
        from bookings.models import Booking

        if not self.user.is_authenticated:
            return None
        return (
            Booking.objects.select_related("property")
            .filter(reference=reference, property__owner=self.user)
            .first()
        )

    async def guest_position(self, event):
        await self.send_json(
            {k: v for k, v in event.items() if k != "type"} | {"type": "guest_position"}
        )


def _distance_km(booking, lat, lng):
    from django.contrib.gis.db.models.functions import Distance

    from properties.models import Property

    p = (
        Property.objects.filter(pk=booking.property_id)
        .annotate(d=Distance("location", Point(lng, lat, srid=4326)))
        .first()
    )
    return round(p.d.km, 2) if p else None


def _maybe_alert_owner(booking, dist_km):
    if cache.add(f"guest_on_way:{booking.pk}", 1, timeout=60 * 60 * 24):
        notify(
            booking.property.owner,
            "guest_on_way",
            "Guest is on the way",
            f"{booking.renter.full_name} is sharing live location ({dist_km} km away).",
            f"/dashboard/owner/bookings/{booking.reference}/",
        )
    if (
        dist_km is not None
        and dist_km <= NEARBY_ALERT_KM
        and cache.add(f"guest_near:{booking.pk}", 1, timeout=60 * 60 * 24)
    ):
        notify(
            booking.property.owner,
            "guest_arriving",
            "Guest arriving soon",
            f"{booking.renter.full_name} is {dist_km} km from {booking.property.name}.",
            f"/dashboard/owner/bookings/{booking.reference}/",
        )
