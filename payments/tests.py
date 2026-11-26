import hashlib
import hmac
import json
from unittest import mock

import pytest
from django.test import override_settings

from bookings import services as booking_services
from payments import services
from payments.models import Payment

pytestmark = pytest.mark.django_db


@pytest.fixture
def booking(renter, room, dates):
    return booking_services.create_booking(renter=renter, room_id=room.pk, check_in=dates[0], check_out=dates[1], guests=1)


def test_demo_checkout_confirms_booking(renter_client, booking):
    o = renter_client.post("/api/payments/order/", {"booking": booking.reference}, format="json").data
    assert o["demo"] and o["amount"] == 448000
    r = renter_client.post("/api/payments/verify/", {"razorpay_order_id": o["order_id"], "razorpay_payment_id": "pay_x", "razorpay_signature": ""}, format="json")
    assert r.status_code == 200
    booking.refresh_from_db()
    assert booking.status == "CONFIRMED"


@override_settings(RAZORPAY_KEY_ID="rzp_test_abc", RAZORPAY_KEY_SECRET="secret")
def test_razorpay_signature_checked(renter_client, booking):
    with mock.patch("payments.services.client") as client:
        client.return_value.order.create.return_value = {"id": "order_real_1"}
        o = renter_client.post("/api/payments/order/", {"booking": booking.reference}, format="json").data
    assert o["order_id"] == "order_real_1" and not o["demo"]

    good = hmac.new(b"secret", b"order_real_1|pay_1", hashlib.sha256).hexdigest()
    bad = renter_client.post("/api/payments/verify/", {"razorpay_order_id": "order_real_1", "razorpay_payment_id": "pay_1", "razorpay_signature": "forged"}, format="json")
    assert bad.status_code == 400
    # a fresh order after the failed one
    Payment.objects.filter(provider_order_id="order_real_1").update(status="CREATED")
    ok = renter_client.post("/api/payments/verify/", {"razorpay_order_id": "order_real_1", "razorpay_payment_id": "pay_1", "razorpay_signature": good}, format="json")
    assert ok.status_code == 200
    booking.refresh_from_db()
    assert booking.status == "CONFIRMED"


def test_other_renter_cannot_pay_for_booking(booking, room):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    from conftest import login

    intruder = get_user_model().objects.create_user("x@example.com", "Sup3r-secret!", full_name="X", role="RENTER")
    assert login(APIClient(), intruder).post("/api/payments/order/", {"booking": booking.reference}, format="json").status_code == 404


def test_webhook_is_signed_and_idempotent(client, booking):
    p = services.create_order(booking)
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_w", "order_id": p.provider_order_id, "method": "upi"}}}}).encode()
    sig = hmac.new(b"whsec_test", body, hashlib.sha256).hexdigest()
    assert client.post("/api/payments/webhook/", body, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE="bad").status_code == 400
    for _ in range(2):
        assert client.post("/api/payments/webhook/", body, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=sig).status_code == 200
    p.refresh_from_db(); booking.refresh_from_db()
    assert p.status == "PAID" and p.method == "upi" and booking.status == "CONFIRMED"


def test_cancel_confirmed_booking_refunds(renter_client, booking):
    p = services.create_order(booking)
    services.mark_paid(p.provider_order_id, "pay_r")
    r = renter_client.post(f"/api/bookings/{booking.reference}/cancel/", {"reason": "Plans changed"}, format="json")
    assert r.status_code == 200
    p.refresh_from_db()
    assert p.status == "REFUNDED" and p.provider_refund_id
