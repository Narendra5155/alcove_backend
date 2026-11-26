"""Razorpay (test mode) integration with an offline demo fallback when keys are absent."""
import logging
import secrets

import razorpay
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from notifications.services import notify

from .models import Payment

log = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


def is_demo_mode() -> bool:
    """No Razorpay keys configured -> simulated payments (only allowed when PAYMENTS_DEMO_FALLBACK is on)."""
    return not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_order(booking: Booking) -> Payment:
    if booking.status != Booking.Status.PENDING:
        raise PaymentError("This booking isn't awaiting payment.")
    if booking.expires_at and booking.expires_at < timezone.now():
        raise PaymentError("Your hold on this room has expired. Please book again.")
    existing = booking.payments.filter(status=Payment.Status.CREATED, amount=booking.total).first()
    if existing:
        return existing
    amount_paise = int(booking.total * 100)
    if is_demo_mode() and not settings.PAYMENTS_DEMO_FALLBACK:
        raise PaymentError("Payments are not configured.")
    if is_demo_mode():
        order_id = "order_demo_" + secrets.token_hex(7)
    else:
        try:
            order = client().order.create(
                {"amount": amount_paise, "currency": "INR", "receipt": booking.reference,
                 "notes": {"booking": booking.reference}}
            )
        except Exception as e:  # noqa: BLE001
            log.exception("Razorpay order creation failed")
            raise PaymentError("Payment gateway unavailable, please retry.") from e
        order_id = order["id"]
    return Payment.objects.create(
        booking=booking, amount=booking.total, provider_order_id=order_id, is_demo=is_demo_mode()
    )


def verify_signature(order_id, payment_id, signature) -> bool:
    if is_demo_mode():
        return True
    try:
        client().utility.verify_payment_signature(
            {"razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature}
        )
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def mark_paid(order_id, payment_id, signature="", method="") -> Payment:
    """Idempotently mark a payment as paid and confirm its booking."""
    from bookings.services import BookingError, confirm_booking

    with transaction.atomic():
        p = Payment.objects.select_for_update().select_related("booking").get(provider_order_id=order_id)
        if p.status == Payment.Status.PAID:
            return p
        p.status = Payment.Status.PAID
        p.provider_payment_id = payment_id
        p.provider_signature = signature
        p.method = method or p.method
        p.paid_at = timezone.now()
        p.save()
    try:
        confirm_booking(p.booking_id)
    except BookingError as e:
        log.warning("Paid booking %s could not be confirmed: %s", p.booking.reference, e)
        refund_payment(p)
        raise PaymentError(str(e)) from e
    return p


def mark_failed(order_id, reason=""):
    p = Payment.objects.filter(provider_order_id=order_id).select_related("booking__renter").first()
    if p and p.status == Payment.Status.CREATED:
        p.status, p.error = Payment.Status.FAILED, reason[:255]
        p.save(update_fields=["status", "error"])
        notify(p.booking.renter, "payment_failed", "Payment failed",
               f"{reason or 'Your payment did not go through.'} You can retry before your hold expires.",
               f"/book/{p.booking.reference}/pay/")
    return p


def refund_payment(p: Payment):
    if p.status != Payment.Status.PAID:
        return p
    if not p.is_demo:
        try:
            refund = client().payment.refund(p.provider_payment_id, {"amount": p.amount_paise})
            p.provider_refund_id = refund.get("id", "")
        except Exception:  # noqa: BLE001
            log.exception("Refund failed for %s", p.provider_payment_id)
            p.error = "Refund failed; will be retried by support."
            p.save(update_fields=["error"])
            return p
    else:
        p.provider_refund_id = "rfnd_demo_" + secrets.token_hex(6)
    p.status, p.refunded_at = Payment.Status.REFUNDED, timezone.now()
    p.save(update_fields=["status", "refunded_at", "provider_refund_id"])
    notify(p.booking.renter, "refund", "Refund initiated",
           f"₹{p.amount} for {p.booking.reference} will reach your account in 5–7 days.",
           f"/dashboard/bookings/{p.booking.reference}/")
    return p


def refund_booking(booking: Booking):
    for p in booking.payments.filter(status=Payment.Status.PAID):
        refund_payment(p)
