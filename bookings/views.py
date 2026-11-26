from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.decorators import owner_required, renter_required

from .models import Booking


@renter_required
@ensure_csrf_cookie
def checkout_page(request, ref):
    b = get_object_or_404(Booking.objects.select_related("property", "room"), reference=ref, renter=request.user)
    if b.status != Booking.Status.PENDING:
        return redirect("renter_booking_detail", ref=ref)
    return render(request, "bookings/checkout.html", {"booking": b})


@login_required
@ensure_csrf_cookie
def renter_booking_detail(request, ref):
    b = get_object_or_404(
        Booking.objects.select_related("property__owner__profile", "room").prefetch_related("payments"),
        reference=ref,
    )
    if b.renter != request.user:
        raise PermissionDenied
    return render(request, "bookings/renter_detail.html", {"booking": b, "review": getattr(b, "review", None)})


@owner_required
@ensure_csrf_cookie
def owner_booking_detail(request, ref):
    b = get_object_or_404(
        Booking.objects.select_related("property", "room", "renter__profile").prefetch_related("payments"),
        reference=ref,
        property__owner=request.user,
    )
    return render(request, "bookings/owner_detail.html", {"booking": b})
