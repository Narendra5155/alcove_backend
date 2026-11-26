from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from notifications.services import notify

from .models import Booking


@shared_task
def expire_pending_bookings():
    stale = Booking.objects.filter(status=Booking.Status.PENDING, expires_at__lt=timezone.now()).select_related("renter", "property")
    count = 0
    for b in stale:
        b.status = Booking.Status.EXPIRED
        b.save(update_fields=["status", "updated_at"])
        notify(b.renter, "booking_expired", "Booking expired",
               f"We released your hold at {b.property.name} as payment wasn't completed.", "/dashboard/")
        count += 1
    return count


@shared_task
def send_checkin_reminders():
    """Once a day-ish: remind renters and hosts about tomorrow's arrivals (idempotent via cache)."""
    from django.core.cache import cache

    tomorrow = timezone.localdate() + timedelta(days=1)
    for b in Booking.objects.filter(status=Booking.Status.CONFIRMED, check_in=tomorrow).select_related("renter", "property__owner"):
        key = f"reminder:{b.pk}"
        if cache.add(key, 1, timeout=60 * 60 * 30):
            notify(b.renter, "checkin_reminder", "Your stay starts tomorrow",
                   f"{b.property.name} · check-in from {b.property.check_in_time:%H:%M}.", f"/dashboard/bookings/{b.reference}/")
            notify(b.property.owner, "arrival_tomorrow", "Guest arriving tomorrow",
                   f"{b.renter.full_name} · {b.room.name} · {b.reference}", f"/dashboard/owner/bookings/{b.reference}/")
