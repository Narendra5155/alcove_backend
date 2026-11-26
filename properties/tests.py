import pytest
from django.contrib.gis.geos import Point

from bookings.models import Booking
from properties.models import Property, Room

pytestmark = pytest.mark.django_db


def test_geo_search_orders_by_distance_and_respects_radius(owner, prop, room):
    far = Property.objects.create(owner=owner, name="Far Away", city="Mysuru", address="x", location=Point(76.6394, 12.2958, srid=4326))
    Room.objects.create(property=far, name="R", price_per_night=1000, quantity=1)
    near = Property.objects.create(owner=owner, name="Next Door", city="Bengaluru", address="y", location=Point(77.6420, 12.9725, srid=4326))
    Room.objects.create(property=near, name="R", price_per_night=1500, quantity=1)

    from rest_framework.test import APIClient

    r = APIClient().get("/api/properties/search/", {"lat": 12.9720, "lng": 77.6410, "radius_km": 10})
    names = [p["name"] for p in r.data["results"]]
    assert names == ["Lakeview Rooms", "Next Door"]
    assert r.data["results"][0]["distance_km"] < 0.1


def test_search_excludes_fully_booked_dates(prop, room, renter, dates):
    from rest_framework.test import APIClient

    ci, co = dates
    Booking.objects.create(renter=renter, property=prop, room=room, check_in=ci, check_out=co, nightly_rate=2000,
                           subtotal=4000, taxes=480, total=4480, status="CONFIRMED")
    r = APIClient().get("/api/properties/search/", {"checkin": ci, "checkout": co})
    assert r.data["results"] == []
    # adjacent dates (check-out day) remain bookable
    r = APIClient().get("/api/properties/search/", {"checkin": co, "checkout": co.replace(day=co.day) + (co - ci)})
    assert len(r.data["results"]) == 1


def test_owner_crud_and_ownership(owner_client, renter_client, prop):
    r = owner_client.post("/api/owner/properties/", {"name": "New Place", "property_type": "HOTEL", "address": "2 Rd", "city": "Goa",
                                                     "lat": 15.5, "lng": 73.8}, format="json")
    assert r.status_code == 201 and r.data["lat"] == 15.5
    pid = r.data["id"]
    assert owner_client.post(f"/api/owner/properties/{pid}/rooms/", {"name": "Twin", "price_per_night": "1800", "quantity": 2}, format="json").status_code == 201
    assert renter_client.get("/api/owner/properties/").status_code == 403


def test_owner_cannot_edit_others_property(prop, renter):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    from conftest import login

    other = get_user_model().objects.create_user("o2@example.com", "Sup3r-secret!", full_name="O2", role="OWNER")
    c = login(APIClient(), other)
    assert c.patch(f"/api/owner/properties/{prop.pk}/", {"name": "Hijack"}, format="json").status_code == 404


def test_property_saved_into_redis_geo_index(prop):
    from locations.services import nearby_properties

    hits = nearby_properties(12.9719, 77.6412, 1)
    assert [h["name"] for h in hits] == ["Lakeview Rooms"]
