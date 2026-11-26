"""Geo search and availability queries."""
from datetime import date

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Avg, Count, Exists, F, IntegerField, Min, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from .models import Property, Room

ACTIVE_BOOKING_STATUSES = ("PENDING", "CONFIRMED", "CHECKED_IN")


def booked_units_subquery(checkin: date, checkout: date):
    from bookings.models import Booking

    return Subquery(
        Booking.objects.filter(
            room=OuterRef("pk"),
            status__in=ACTIVE_BOOKING_STATUSES,
            check_in__lt=checkout,
            check_out__gt=checkin,
        )
        .values("room")
        .annotate(total=Sum("units"))
        .values("total")[:1],
        output_field=IntegerField(),
    )


def rooms_with_availability(qs, checkin: date, checkout: date):
    return qs.annotate(booked=Coalesce(booked_units_subquery(checkin, checkout), Value(0))).annotate(
        available=F("quantity") - F("booked")
    )


def search_properties(
    *,
    lat=None,
    lng=None,
    radius_km=25,
    city=None,
    q=None,
    checkin=None,
    checkout=None,
    guests=1,
    min_price=None,
    max_price=None,
    property_type=None,
    amenities=None,
):
    qs = Property.objects.filter(is_active=True)

    room_filter = Q(is_active=True, max_guests__gte=guests or 1)
    if min_price is not None:
        room_filter &= Q(price_per_night__gte=min_price)
    if max_price is not None:
        room_filter &= Q(price_per_night__lte=max_price)

    rooms = Room.objects.filter(room_filter)
    if checkin and checkout:
        rooms = rooms_with_availability(rooms, checkin, checkout).filter(available__gte=1)
    qs = qs.filter(Exists(rooms.filter(property=OuterRef("pk"))))

    if lat is not None and lng is not None:
        origin = Point(float(lng), float(lat), srid=4326)
        qs = qs.filter(location__dwithin=(origin, D(km=float(radius_km)))).annotate(
            distance=Distance("location", origin)
        )
    if city:
        qs = qs.filter(city__iexact=city)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(address__icontains=q))
    if property_type:
        qs = qs.filter(property_type=property_type)
    if amenities:
        for a in amenities:
            qs = qs.filter(amenities__id=a)

    qs = qs.annotate(
        min_price=Min("rooms__price_per_night", filter=Q(rooms__is_active=True)),
        avg_rating=Avg("reviews__rating"),
        review_count=Count("reviews", distinct=True),
    ).prefetch_related("images")
    return qs.order_by("distance") if lat is not None and lng is not None else qs.order_by("-created_at")
