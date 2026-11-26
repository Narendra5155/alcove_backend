import re

import pytest
from django.conf import settings
from django.core import mail
from rest_framework.test import APIClient

from accounts.models import User

pytestmark = pytest.mark.django_db


def _code():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


def test_register_requires_email_otp_then_issues_cookies():
    c = APIClient()
    r = c.post("/api/auth/register/", {"full_name": "New Person", "email": "New@Example.com", "password": "Tr1cky-pass!", "role": "RENTER"}, format="json")
    assert r.status_code == 201
    u = User.objects.get(email="new@example.com")
    assert not u.is_email_verified and u.profile is not None
    r = c.post("/api/auth/verify-otp/", {"challenge_id": r.data["challenge_id"], "code": _code()}, format="json")
    assert r.status_code == 200
    assert settings.JWT_ACCESS_COOKIE in r.cookies and r.cookies[settings.JWT_ACCESS_COOKIE]["httponly"]
    u.refresh_from_db()
    assert u.is_email_verified


def test_login_wrong_password_sends_nothing(renter):
    r = APIClient().post("/api/auth/login/", {"email": renter.email, "password": "nope"}, format="json")
    assert r.status_code == 400 and not mail.outbox


def test_login_otp_attempt_limit(renter):
    c = APIClient()
    cid = c.post("/api/auth/login/", {"email": renter.email, "password": "Sup3r-secret!"}, format="json").data["challenge_id"]
    real = _code()
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        assert c.post("/api/auth/verify-otp/", {"challenge_id": cid, "code": wrong}, format="json").status_code == 400
    # challenge is burned: even the right code fails now
    r = c.post("/api/auth/verify-otp/", {"challenge_id": cid, "code": real}, format="json")
    assert r.status_code == 400


def test_otp_is_single_use(renter):
    c = APIClient()
    cid = c.post("/api/auth/login/", {"email": renter.email, "password": "Sup3r-secret!"}, format="json").data["challenge_id"]
    code = _code()
    assert c.post("/api/auth/verify-otp/", {"challenge_id": cid, "code": code}, format="json").status_code == 200
    assert c.post("/api/auth/verify-otp/", {"challenge_id": cid, "code": code}, format="json").status_code == 400


def test_resend_has_cooldown(renter):
    c = APIClient()
    cid = c.post("/api/auth/login/", {"email": renter.email, "password": "Sup3r-secret!"}, format="json").data["challenge_id"]
    r = c.post("/api/auth/resend-otp/", {"challenge_id": cid}, format="json")
    assert r.status_code == 400 and "wait" in r.data["detail"]


def test_password_reset_flow(renter):
    c = APIClient()
    cid = c.post("/api/auth/password-reset/", {"email": renter.email}, format="json").data["challenge_id"]
    r = c.post("/api/auth/password-reset/confirm/", {"challenge_id": cid, "code": _code(), "new_password": "Another-g00d-one"}, format="json")
    assert r.status_code == 200
    renter.refresh_from_db()
    assert renter.check_password("Another-g00d-one")


def test_password_reset_unknown_email_is_indistinguishable():
    r = APIClient().post("/api/auth/password-reset/", {"email": "ghost@example.com"}, format="json")
    assert r.status_code == 200 and "challenge_id" in r.data and not mail.outbox


def test_cookie_auth_and_logout_blacklists(renter_client):
    assert renter_client.get("/api/profile/").status_code == 200
    renter_client.post("/api/auth/logout/")
    assert renter_client.get("/api/profile/").status_code in (401, 403)


def test_middleware_refreshes_expired_access(renter_client, client):
    # Simulate an expired/missing access cookie: only refresh cookie present.
    client.cookies[settings.JWT_REFRESH_COOKIE] = renter_client.cookies[settings.JWT_REFRESH_COOKIE].value
    r = client.get("/profile/")
    assert r.status_code == 200
    assert settings.JWT_ACCESS_COOKIE in r.cookies


def test_avatar_upload_resizes(renter_client, renter):
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (1200, 800), "orange").save(buf, "PNG")
    f = SimpleUploadedFile("a.png", buf.getvalue(), content_type="image/png")
    r = renter_client.post("/api/profile/avatar/", {"avatar": f}, format="multipart")
    assert r.status_code == 200
    renter.profile.refresh_from_db()
    assert Image.open(renter.profile.avatar.path).size == (400, 400)


def test_avatar_rejects_non_image(renter_client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    f = SimpleUploadedFile("a.png", b"not an image", content_type="image/png")
    assert renter_client.post("/api/profile/avatar/", {"avatar": f}, format="multipart").status_code == 400


def test_renter_can_start_hosting(renter_client, renter):
    r = renter_client.post("/api/profile/role/", {"role": "OWNER"}, format="json")
    assert r.status_code == 200 and r.data["redirect"] == "/dashboard/owner/"
    renter.refresh_from_db()
    assert renter.is_owner
    assert renter_client.get("/api/owner/properties/").status_code == 200


def test_cannot_start_hosting_with_trip_in_progress(renter_client, renter, room, dates):
    from bookings.services import create_booking

    create_booking(renter=renter, room_id=room.pk, check_in=dates[0], check_out=dates[1], guests=1)
    assert renter_client.post("/api/profile/role/", {"role": "OWNER"}, format="json").status_code == 400


def test_host_switching_to_travel_hides_listings(owner_client, owner, prop):
    assert owner_client.post("/api/profile/role/", {"role": "RENTER"}, format="json").status_code == 200
    prop.refresh_from_db()
    assert not prop.is_active
