"""Booking lifecycle: creation with row locking, state transitions, notifications."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from notifications.services import notify
from properties.models import Room

from .models import Booking


class BookingError(Exception):
    pass


def available_units(room, check_in, check_out, exclude_id=None) -> int:
    qs = Booking.objects.filter(
        room=room, status__in=Booking.ACTIVE_STATUSES, check_in__lt=check_out, check_out__gt=check_in
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return room.quantity - (qs.aggregate(t=Sum("units"))["t"] or 0)


def quote(room, check_in, check_out, units=1):
    nights = (check_out - check_in).days
    subtotal = (room.price_per_night * nights * units).quantize(Decimal("0.01"))
    taxes = (subtotal * Booking.TAX_RATE).quantize(Decimal("0.01"))
    return {"nights": nights, "nightly_rate": room.price_per_night, "subtotal": subtotal, "taxes": taxes, "total": subtotal + taxes}


@transaction.atomic
def create_booking(*, renter, room_id, check_in, check_out, guests, units=1, special_requests="", share_location=False):
    if renter.role != "RENTER":
        raise BookingError("Only renter accounts can book stays.")
    if check_in < timezone.localdate() or check_out <= check_in:
        raise BookingError("Choose valid future dates.")
    if (check_out - check_in).days > 30:
        raise BookingError("Stays are limited to 30 nights.")
    # Lock the room row so concurrent bookings for it serialize here.
    room = Room.objects.select_for_update().select_related("property").filter(pk=room_id, is_active=True).first()
    if not room or not room.property.is_active:
        raise BookingError("This room is no longer available.")
    if guests > room.max_guests * units:
        raise BookingError(f"This room fits up to {room.max_guests} guests per unit.")
    if available_units(room, check_in, check_out) < units:
        raise BookingError("Sorry, this room was just booked for those dates.")

    booking = Booking.objects.create(
        renter=renter,
        property=room.property,
        room=room,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        units=units,
        special_requests=special_requests,
        share_location=share_location,
        expires_at=timezone.now() + timedelta(minutes=settings.BOOKING_PAYMENT_WINDOW_MINUTES),
        **{k: v for k, v in quote(room, check_in, check_out, units).items() if k != "nights"},
    )
    return booking


def _locked(booking_id):
    return Booking.objects.select_for_update().select_related("property__owner", "renter", "room").get(pk=booking_id)


@transaction.atomic
def confirm_booking(booking_id):
    b = _locked(booking_id)
    if b.status == Booking.Status.CONFIRMED:
        return b
    if b.status not in (Booking.Status.PENDING, Booking.Status.EXPIRED):
        raise BookingError(f"Cannot confirm a booking that is {b.get_status_display().lower()}.")
    if b.status == Booking.Status.EXPIRED and available_units(b.room, b.check_in, b.check_out, exclude_id=b.pk) < b.units:
        raise BookingError("Room no longer available; payment will be refunded.")
    b.status = Booking.Status.CONFIRMED
    b.expires_at = None
    b.save(update_fields=["status", "expires_at", "updated_at"])
    notify(b.renter, "booking_confirmed", "Booking confirmed",
           f"{b.property.name}, {b.check_in:%d %b} – {b.check_out:%d %b}. Ref {b.reference}.", f"/dashboard/bookings/{b.reference}/")
    notify(b.owner, "new_booking", "New booking received",
           f"{b.renter.full_name} booked {b.room.name} at {b.property.name} for {b.nights} night(s).",
           f"/dashboard/owner/bookings/{b.reference}/")
    return b


@transaction.atomic
def check_in(booking_id, owner):
    b = _locked(booking_id)
    if b.owner != owner:
        raise BookingError("Not your booking.")
    if b.status != Booking.Status.CONFIRMED:
        raise BookingError("Only confirmed bookings can be checked in.")
    if b.check_in > timezone.localdate():
        raise BookingError("Check-in date hasn't arrived yet.")
    b.status, b.checked_in_at, b.share_location = Booking.Status.CHECKED_IN, timezone.now(), False
    b.save(update_fields=["status", "checked_in_at", "share_location", "updated_at"])
    notify(b.renter, "checked_in", "Welcome! You're checked in", f"Enjoy your stay at {b.property.name}.", f"/dashboard/bookings/{b.reference}/")
    return b


@transaction.atomic
def check_out(booking_id, owner):
    b = _locked(booking_id)
    if b.owner != owner:
        raise BookingError("Not your booking.")
    if b.status != Booking.Status.CHECKED_IN:
        raise BookingError("Guest hasn't checked in.")
    b.status, b.checked_out_at = Booking.Status.COMPLETED, timezone.now()
    b.save(update_fields=["status", "checked_out_at", "updated_at"])
    notify(b.renter, "checked_out", "Thanks for staying with us",
           f"How was {b.property.name}? Leave a review.", f"/dashboard/bookings/{b.reference}/")
    return b


@transaction.atomic
def cancel_booking(booking_id, by_user, reason=""):
    from payments.services import refund_booking

    b = _locked(booking_id)
    is_owner, is_renter = b.owner == by_user, b.renter == by_user
    if not (is_owner or is_renter):
        raise BookingError("Not your booking.")
    if b.status not in (Booking.Status.PENDING, Booking.Status.CONFIRMED):
        raise BookingError("This booking can no longer be cancelled.")
    was_paid = b.status == Booking.Status.CONFIRMED
    b.status, b.cancelled_at = Booking.Status.CANCELLED, timezone.now()
    b.cancel_reason = reason[:255] or ("Cancelled by host" if is_owner else "Cancelled by guest")
    b.share_location = False
    b.save(update_fields=["status", "cancelled_at", "cancel_reason", "share_location", "updated_at"])
    if was_paid:
        refund_booking(b)
    other = b.renter if is_owner else b.owner
    notify(other, "booking_cancelled", "Booking cancelled",
           f"{b.reference} at {b.property.name} was cancelled. {b.cancel_reason}",
           f"/dashboard/bookings/{b.reference}/" if is_owner else f"/dashboard/owner/bookings/{b.reference}/")
    return b


def set_location_sharing(booking, enabled: bool):
    if enabled and booking.status != Booking.Status.CONFIRMED:
        raise BookingError("Location can only be shared for confirmed upcoming stays.")
    booking.share_location = enabled
    booking.save(update_fields=["share_location", "updated_at"])
    return booking
