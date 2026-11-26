import csv
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from bookings.models import Booking
from core.decorators import owner_required

from . import services


@login_required
@ensure_csrf_cookie
def home(request):
    if request.user.is_owner:
        return redirect("owner_dashboard")
    today = timezone.localdate()
    bookings = Booking.objects.filter(renter=request.user).select_related("property", "room").prefetch_related("property__images")
    return render(request, "dashboard/renter.html", {
        "upcoming": bookings.filter(status__in=[Booking.Status.CONFIRMED, Booking.Status.CHECKED_IN, Booking.Status.PENDING], check_out__gte=today).order_by("check_in"),
        "past": bookings.filter(status__in=[Booking.Status.COMPLETED, Booking.Status.CANCELLED, Booking.Status.EXPIRED]).order_by("-check_in")[:20],
        "arrival_today": bookings.filter(status=Booking.Status.CONFIRMED, check_in=today).first(),
    })


@owner_required
@ensure_csrf_cookie
def owner_home(request):
    today = timezone.localdate()
    bookings = Booking.objects.filter(property__owner=request.user).select_related("property", "room", "renter__profile")
    return render(request, "dashboard/owner.html", {
        "kpis": services.owner_kpis(request.user),
        "series": services.revenue_series(request.user),
        "today": today,
        "arrivals": bookings.filter(status=Booking.Status.CONFIRMED, check_in__gte=today, check_in__lte=today + timedelta(days=7)).order_by("check_in")[:8],
        "departures": bookings.filter(status=Booking.Status.CHECKED_IN).order_by("check_out")[:8],
        "recent": bookings.order_by("-created_at")[:6],
    })


@owner_required
@ensure_csrf_cookie
def owner_bookings(request):
    return render(request, "dashboard/owner_bookings.html", {
        "statuses": Booking.Status.choices,
        "properties": request.user.properties.only("id", "name"),
    })


@owner_required
@ensure_csrf_cookie
def owner_calendar(request):
    return render(request, "dashboard/owner_calendar.html", {"properties": request.user.properties.only("id", "name")})


@owner_required
def owner_calendar_api(request):
    try:
        month = date.fromisoformat(request.GET.get("month", "") + "-01")
    except ValueError:
        month = timezone.localdate().replace(day=1)
    start, end = services.month_bounds(month)
    pid = request.GET.get("property") or None
    return JsonResponse({
        "month": month.strftime("%Y-%m"),
        "events": services.calendar_events(request.user, start, end, pid),
        "occupancy": services.occupancy(request.user, start, end),
    })


@owner_required
def owner_earnings(request):
    ledger = services.earnings_ledger(request.user)
    totals = {"gross": 0, "payout": 0, "refunded": 0}
    for p in ledger:
        if p.status == "PAID":
            totals["gross"] += p.booking.subtotal
            totals["payout"] += p.booking.owner_payout
        else:
            totals["refunded"] += p.amount
    return render(request, "dashboard/owner_earnings.html", {"ledger": ledger[:200], "totals": totals})


@owner_required
def owner_earnings_csv(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="alcove-earnings-{timezone.localdate()}.csv"'
    w = csv.writer(resp)
    w.writerow(["Paid at", "Reference", "Property", "Room", "Guest", "Check-in", "Check-out", "Nights",
                "Room charges", "Taxes", "Guest paid", "Your payout", "Status", "Payment ID"])
    for p in services.earnings_ledger(request.user):
        b = p.booking
        w.writerow([p.paid_at and timezone.localtime(p.paid_at).strftime("%Y-%m-%d %H:%M"), b.reference, b.property.name,
                    b.room.name, b.renter.full_name, b.check_in, b.check_out, b.nights, b.subtotal, b.taxes, p.amount,
                    b.owner_payout if p.status == "PAID" else 0, p.status, p.provider_payment_id])
    return resp
