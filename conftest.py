from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tokens import issue_tokens
from core.redis import get_redis
from properties.models import Property, Room


@pytest.fixture(autouse=True)
def _run_on_commit_immediately(monkeypatch):
    """Tests run inside a transaction that never commits; fire on_commit hooks (emails, pushes) right away."""
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, using=None, robust=False: fn())


@pytest.fixture(autouse=True)
def _clean_redis():
    get_redis().flushdb()
    from django.core.cache import cache

    cache.clear()
    yield


@pytest.fixture
def owner(db):
    return User.objects.create_user("host@example.com", "Sup3r-secret!", full_name="Hema Host", role="OWNER", is_email_verified=True)


@pytest.fixture
def renter(db):
    return User.objects.create_user("guest@example.com", "Sup3r-secret!", full_name="Gita Guest", role="RENTER", is_email_verified=True)


def login(client, user):
    """Attach JWT cookies for `user` to an APIClient (CSRF checks are off in APIClient by default)."""
    from django.http import HttpResponse

    resp = issue_tokens(HttpResponse(), user)
    for k, morsel in resp.cookies.items():
        client.cookies[k] = morsel.value
    return client


@pytest.fixture
def owner_client(owner):
    return login(APIClient(), owner)


@pytest.fixture
def renter_client(renter):
    return login(APIClient(), renter)


@pytest.fixture
def prop(owner):
    p = Property.objects.create(owner=owner, name="Lakeview Rooms", city="Bengaluru", address="1 Lake Rd",
                                location=Point(77.6412, 12.9719, srid=4326))
    return p


@pytest.fixture
def room(prop):
    return Room.objects.create(property=prop, name="Deluxe", price_per_night=Decimal("2000"), max_guests=2, quantity=1)


@pytest.fixture
def dates():
    d = timezone.localdate() + timedelta(days=5)
    return d, d + timedelta(days=2)
