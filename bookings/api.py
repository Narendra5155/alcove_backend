from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsOwnerRole, IsRenterRole
from notifications.services import notify
from properties.models import Room

from . import services
from .models import Booking, Review
from .serializers import BookingCreateSerializer, BookingSerializer, ReviewSerializer


def _err(e):
    return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QuoteView(APIView):
    permission_classes = [AllowAny]

    class Params(serializers.Serializer):
        room_id = serializers.IntegerField()
        check_in = serializers.DateField()
        check_out = serializers.DateField()
        units = serializers.IntegerField(min_value=1, max_value=10, default=1)

    def get(self, request):
        p = self.Params(data=request.query_params.dict())
        p.is_valid(raise_exception=True)
        d = p.validated_data
        if d["check_out"] <= d["check_in"]:
            return _err("Check-out must be after check-in.")
        room = get_object_or_404(Room, pk=d["room_id"], is_active=True)
        q = services.quote(room, d["check_in"], d["check_out"], d["units"])
        q["available"] = services.available_units(room, d["check_in"], d["check_out"])
        return Response(q)


class BookingCreateView(APIView):
    permission_classes = [IsRenterRole]

    def post(self, request):
        s = BookingCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            b = services.create_booking(renter=request.user, **s.validated_data)
        except services.BookingError as e:
            return _err(e)
        return Response({**BookingSerializer(b).data, "checkout_url": f"/book/{b.reference}/pay/"}, status=201)


class RenterBookingAction(APIView):
    permission_classes = [IsRenterRole]

    def get_booking(self, request, ref):
        return get_object_or_404(Booking.objects.select_related("property", "room"), reference=ref, renter=request.user)


class RenterCancelView(RenterBookingAction):
    def post(self, request, ref):
        b = self.get_booking(request, ref)
        try:
            b = services.cancel_booking(b.pk, request.user, request.data.get("reason", ""))
        except services.BookingError as e:
            return _err(e)
        return Response(BookingSerializer(b).data)


class ShareLocationView(RenterBookingAction):
    def post(self, request, ref):
        b = self.get_booking(request, ref)
        try:
            services.set_location_sharing(b, bool(request.data.get("enabled")))
        except services.BookingError as e:
            return _err(e)
        return Response({"share_location": b.share_location})


class ReviewView(RenterBookingAction):
    def post(self, request, ref):
        b = self.get_booking(request, ref)
        if b.status != Booking.Status.COMPLETED:
            return _err("You can review a stay after checking out.")
        if hasattr(b, "review"):
            return _err("You've already reviewed this stay.")
        s = ReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save(booking=b, property=b.property, renter=request.user)
        notify(b.owner, "new_review", f"New {s.validated_data['rating']}★ review",
               f"{request.user.full_name} reviewed {b.property.name}.", f"/stays/{b.property.slug}/")
        return Response(s.data, status=201)


class OwnerBookingAction(APIView):
    permission_classes = [IsOwnerRole]
    op = None

    def post(self, request, ref):
        b = get_object_or_404(Booking, reference=ref, property__owner=request.user)
        try:
            if self.op == "check_in":
                b = services.check_in(b.pk, request.user)
            elif self.op == "check_out":
                b = services.check_out(b.pk, request.user)
            else:
                b = services.cancel_booking(b.pk, request.user, request.data.get("reason", ""))
        except services.BookingError as e:
            return _err(e)
        return Response(BookingSerializer(b).data)


class MyBookingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_owner:
            qs = Booking.objects.filter(property__owner=request.user)
        else:
            qs = Booking.objects.filter(renter=request.user)
        st = request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        qs = qs.select_related("property", "room", "renter").prefetch_related("property__images")[:200]
        return Response({"results": BookingSerializer(qs, many=True).data})
