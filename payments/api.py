import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from core.permissions import IsRenterRole

from . import services
from .models import Payment

log = logging.getLogger(__name__)


class CreateOrderView(APIView):
    permission_classes = [IsRenterRole]

    def post(self, request):
        booking = get_object_or_404(
            Booking.objects.select_related("property"), reference=request.data.get("booking"), renter=request.user
        )
        try:
            p = services.create_order(booking)
        except services.PaymentError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({
            "demo": p.is_demo,
            "key": settings.RAZORPAY_KEY_ID,
            "order_id": p.provider_order_id,
            "amount": p.amount_paise,
            "currency": p.currency,
            "name": "Alcove",
            "description": f"{booking.property.name} · {booking.reference}",
            "prefill": {"name": request.user.full_name, "email": request.user.email,
                        "contact": request.user.profile.phone},
        })


class VerifySerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField(allow_blank=True)


class VerifyPaymentView(APIView):
    permission_classes = [IsRenterRole]

    def post(self, request):
        s = VerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        p = get_object_or_404(Payment, provider_order_id=d["razorpay_order_id"], booking__renter=request.user)
        if p.is_demo != services.is_demo_mode() or not services.verify_signature(
            d["razorpay_order_id"], d["razorpay_payment_id"], d["razorpay_signature"]
        ):
            services.mark_failed(p.provider_order_id, "Signature verification failed.")
            return Response({"detail": "Payment verification failed."}, status=400)
        try:
            services.mark_paid(p.provider_order_id, d["razorpay_payment_id"], d["razorpay_signature"],
                               "demo" if p.is_demo else "")
        except services.PaymentError as e:
            return Response({"detail": str(e)}, status=409)
        return Response({"redirect": f"/dashboard/bookings/{p.booking.reference}/?paid=1"})


class FailedPaymentView(APIView):
    permission_classes = [IsRenterRole]

    def post(self, request):
        order_id = request.data.get("razorpay_order_id", "")
        get_object_or_404(Payment, provider_order_id=order_id, booking__renter=request.user)
        services.mark_failed(order_id, str(request.data.get("reason", ""))[:200])
        return Response({"ok": True})


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def webhook(request):
    """Razorpay webhook: payment.captured / payment.failed (backup to client-side verify)."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    body = request.body
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not secret or not hmac.compare_digest(hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), sig):
        return Response(status=status.HTTP_400_BAD_REQUEST)
    event = json.loads(body)
    entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id")
    if not order_id or not Payment.objects.filter(provider_order_id=order_id).exists():
        return Response({"ignored": True})
    if event.get("event") == "payment.captured":
        try:
            services.mark_paid(order_id, entity.get("id", ""), method=entity.get("method", ""))
        except services.PaymentError:
            pass
    elif event.get("event") == "payment.failed":
        services.mark_failed(order_id, entity.get("error_description", ""))
    return Response({"ok": True})
