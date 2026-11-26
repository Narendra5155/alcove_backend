from datetime import timedelta

import pytest
from django.utils import timezone

from bookings import services
from bookings.models import Booking
from bookings.tasks import expire_pending_bookings
from notifications.models import Notification

pytestmark = pytest.mark.django_db


def test_create_booking_quotes_and_holds(renter_client, room, dates):
    ci, co = dates
    r = renter_client.post("/api/bookings/", {"room_id": room.pk, "check_in": ci, "check_out": co, "guests": 2}, format="json")
    assert r.status_code == 201
    b = Booking.objects.get(reference=r.data["reference"])
    assert b.status == "PENDING" and b.subtotal == 4000 and b.taxes == 480 and b.total == 4480
    assert b.expires_at > timezone.now()


def test_overlapping_booking_rejected(renter, room, dates):
    ci, co = dates
    services.create_booking(renter=renter, room_id=room.pk, check_in=ci, check_out=co, guests=1)
    with pytest.raises(services.BookingError):
        services.create_booking(renter=renter, room_id=room.pk, check_in=ci + timedelta(days=1), check_out=co + timedelta(days=1), guests=1)


def test_owner_cannot_book(owner_client, room, dates):
    ci, co = dates
    assert owner_client.post("/api/bookings/", {"room_id": room.pk, "check_in": ci, "check_out": co, "guests": 1}, format="json").status_code == 403


def test_guest_limit(renter, room, dates):
    with pytest.raises(services.BookingError):
        services.create_booking(renter=renter, room_id=room.pk, check_in=dates[0], check_out=dates[1], guests=5)


def test_expiry_releases_room(renter, room, dates):
    b = services.create_booking(renter=renter, room_id=room.pk, check_in=dates[0], check_out=dates[1], guests=1)
    Booking.objects.filter(pk=b.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert expire_pending_bookings() == 1
    assert services.available_units(room, *dates) == 1


def test_lifecycle_and_notifications(renter, owner, room):
    today = timezone.localdate()
    b = services.create_booking(renter=renter, room_id=room.pk, check_in=today, check_out=today + timedelta(days=1), guests=1)
    services.confirm_booking(b.pk)
    assert Notification.objects.filter(user=owner, verb="new_booking").exists()
    assert Notification.objects.filter(user=renter, verb="booking_confirmed").exists()
    services.check_in(b.pk, owner)
    services.check_out(b.pk, owner)
    b.refresh_from_db()
    assert b.status == "COMPLETED"


def test_review_only_after_completion(renter_client, renter, owner, room):
    today = timezone.localdate()
    b = services.create_booking(renter=renter, room_id=room.pk, check_in=today, check_out=today + timedelta(days=1), guests=1)
    url = f"/api/bookings/{b.reference}/review/"
    assert renter_client.post(url, {"rating": 5}, format="json").status_code == 400
    services.confirm_booking(b.pk); services.check_in(b.pk, owner); services.check_out(b.pk, owner)
    assert renter_client.post(url, {"rating": 5, "comment": "Lovely"}, format="json").status_code == 201
    assert renter_client.post(url, {"rating": 4}, format="json").status_code == 400
