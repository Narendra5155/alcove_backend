"""Owner analytics."""
import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from bookings.models import Booking
from payments.models import Payment
from properties.models import Room

OCCUPYING = (Booking.Status.CONFIRMED, Booking.Status.CHECKED_IN, Booking.Status.COMPLETED)
FEE = Decimal(settings.PLATFORM_FEE_PERCENT) / 100


def month_bounds(d: date):
    start = d.replace(day=1)
    end = start.replace(day=calendar.monthrange(d.year, d.month)[1]) + timedelta(days=1)
    return start, end


def occupancy(owner, start: date, end: date) -> float:
    units = Room.objects.filter(property__owner=owner, is_active=True, property__is_active=True).aggregate(
        u=Sum("quantity"))["u"] or 0
    capacity = units * (end - start).days
    if not capacity:
        return 0.0
    booked = 0
    for b in Booking.objects.filter(property__owner=owner, status__in=OCCUPYING, check_in__lt=end, check_out__gt=start).only(
        "check_in", "check_out", "units"
    ):
        booked += ((min(b.check_out, end) - max(b.check_in, start)).days) * b.units
    return round(100 * booked / capacity, 1)


def owner_kpis(owner):
    today = timezone.localdate()
    start, end = month_bounds(today)
    prev_start, prev_end = month_bounds(start - timedelta(days=1))
    paid = Payment.objects.filter(booking__property__owner=owner, status=Payment.Status.PAID)

    def revenue(s, e):
        sub = paid.filter(paid_at__date__gte=s, paid_at__date__lt=e).aggregate(t=Sum("booking__subtotal"))["t"] or Decimal(0)
        return (sub * (1 - FEE)).quantize(Decimal("0.01"))

    rev, prev_rev = revenue(start, end), revenue(prev_start, prev_end)
    bookings = Booking.objects.filter(property__owner=owner)
    return {
        "revenue_month": rev,
        "revenue_change": round(100 * (rev - prev_rev) / prev_rev, 1) if prev_rev else None,
        "occupancy_month": occupancy(owner, start, end),
        "upcoming_checkins": bookings.filter(status=Booking.Status.CONFIRMED, check_in__gte=today,
                                             check_in__lte=today + timedelta(days=7)).count(),
        "in_house": bookings.filter(status=Booking.Status.CHECKED_IN).count(),
        "pending_payments": bookings.filter(status=Booking.Status.PENDING).count(),
        "properties": owner.properties.count(),
        "lifetime_bookings": bookings.filter(status__in=OCCUPYING).count(),
    }


def revenue_series(owner, months=12):
    today = timezone.localdate()
    idx = today.year * 12 + today.month - 1 - (months - 1)  # month index of the first bar
    first = date(idx // 12, idx % 12 + 1, 1)
    rows = (
        Payment.objects.filter(booking__property__owner=owner, status=Payment.Status.PAID, paid_at__date__gte=first)
        .annotate(m=TruncMonth("paid_at"))
        .values("m")
        .annotate(gross=Sum("booking__subtotal"), n=Count("id"))
    )
    by_month = {r["m"].date().replace(day=1): r for r in rows}
    labels, payout, count = [], [], []
    cur = first
    for _ in range(months):
        r = by_month.get(cur)
        labels.append(cur.strftime("%b %y"))
        payout.append(float((r["gross"] * (1 - FEE)) if r else 0))
        count.append(r["n"] if r else 0)
        cur = (cur + timedelta(days=32)).replace(day=1)
    return {"labels": labels, "payout": payout, "bookings": count}


def status_breakdown(owner):
    rows = Booking.objects.filter(property__owner=owner).values("status").annotate(n=Count("id"))
    return {r["status"]: r["n"] for r in rows}


def calendar_events(owner, start: date, end: date, property_id=None):
    qs = Booking.objects.filter(property__owner=owner, check_in__lt=end, check_out__gt=start).filter(
        ~Q(status__in=[Booking.Status.CANCELLED, Booking.Status.EXPIRED])
    ).select_related("property", "room", "renter")
    if property_id:
        qs = qs.filter(property_id=property_id)
    return [
        {
            "reference": b.reference,
            "title": f"{b.renter.full_name} · {b.room.name}",
            "property": b.property.name,
            "start": b.check_in.isoformat(),
            "end": b.check_out.isoformat(),
            "status": b.status,
            "color": b.status_color,
            "url": f"/dashboard/owner/bookings/{b.reference}/",
        }
        for b in qs
    ]


def earnings_ledger(owner):
    return (
        Payment.objects.filter(booking__property__owner=owner, status__in=[Payment.Status.PAID, Payment.Status.REFUNDED])
        .select_related("booking__property", "booking__renter", "booking__room")
        .order_by("-paid_at")
    )
