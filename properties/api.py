from datetime import date

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsOwnerRole

from .models import Amenity, Property, PropertyImage, Room
from .serializers import (
    AmenitySerializer,
    OwnerPropertySerializer,
    PropertyCardSerializer,
    PropertyDetailSerializer,
    RoomSerializer,
)
from .services import rooms_with_availability, search_properties


class SearchParams(serializers.Serializer):
    lat = serializers.FloatField(required=False, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=False, min_value=-180, max_value=180)
    radius_km = serializers.FloatField(
        required=False, default=25, min_value=0.5, max_value=500
    )
    city = serializers.CharField(required=False, allow_blank=True)
    q = serializers.CharField(required=False, allow_blank=True)
    checkin = serializers.DateField(required=False)
    checkout = serializers.DateField(required=False)
    guests = serializers.IntegerField(
        required=False, default=1, min_value=1, max_value=20
    )
    min_price = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2
    )
    max_price = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2
    )
    property_type = serializers.ChoiceField(
        required=False, choices=Property.Type.choices
    )
    amenities = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate(self, attrs):
        ci, co = attrs.get("checkin"), attrs.get("checkout")
        if bool(ci) != bool(co):
            raise serializers.ValidationError(
                "Provide both check-in and check-out dates."
            )
        if ci and (co <= ci or ci < date.today()):
            raise serializers.ValidationError("Choose valid future dates.")
        return attrs


class PropertySearchView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        params = request.query_params.copy()
        amenities = request.query_params.getlist("amenities")
        s = SearchParams(
            data={**params.dict(), "amenities": amenities}
            if amenities
            else params.dict()
        )
        s.is_valid(raise_exception=True)
        qs = search_properties(**s.validated_data)[:100]
        return Response({"results": PropertyCardSerializer(qs, many=True).data})


class PropertyDetailView(generics.RetrieveAPIView):
    permission_classes = (AllowAny,)
    serializer_class = PropertyDetailSerializer
    lookup_field = "slug"
    queryset = Property.objects.filter(is_active=True).prefetch_related(
        "images", "amenities", "rooms"
    )


class AvailabilityView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, slug):
        prop = get_object_or_404(Property, slug=slug, is_active=True)
        s = SearchParams(data=request.query_params.dict())
        s.is_valid(raise_exception=True)
        ci, co = s.validated_data.get("checkin"), s.validated_data.get("checkout")
        if not ci:
            return Response(
                {"detail": "checkin and checkout are required."}, status=400
            )
        rooms = rooms_with_availability(prop.rooms.filter(is_active=True), ci, co)
        return Response(
            {"nights": (co - ci).days, "rooms": RoomSerializer(rooms, many=True).data}
        )


class AmenityListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = AmenitySerializer
    queryset = Amenity.objects.all()
    pagination_class = None


class OwnerPropertyListCreate(generics.ListCreateAPIView):
    permission_classes = (IsOwnerRole,)
    serializer_class = OwnerPropertySerializer
    pagination_class = None

    def get_queryset(self):
        return self.request.user.properties.prefetch_related(
            "images", "rooms", "amenities"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class OwnerPropertyDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsOwnerRole,)
    serializer_class = OwnerPropertySerializer

    def get_queryset(self):
        return self.request.user.properties.prefetch_related(
            "images", "rooms", "amenities"
        )

    def perform_destroy(self, instance):
        from bookings.models import Booking

        if instance.bookings.filter(status__in=Booking.ACTIVE_STATUSES).exists():
            raise serializers.ValidationError(
                "This property has active bookings; deactivate it instead."
            )
        instance.delete()


class OwnerPropertyImages(APIView):
    permission_classes = (IsOwnerRole,)
    parser_classes = (MultiPartParser,)

    def post(self, request, pk):
        prop = get_object_or_404(Property, pk=pk, owner=request.user)
        files = request.FILES.getlist("images")
        if not files:
            return Response({"detail": "No images uploaded."}, status=400)
        if prop.images.count() + len(files) > 20:
            return Response(
                {"detail": "A property can have at most 20 photos."}, status=400
            )
        created = []
        try:
            for f in files:
                created.append(PropertyImage.create_from_upload(prop, f))
        except ValidationError as e:
            return Response({"detail": e.messages[0]}, status=400)
        return Response(
            {
                "images": [
                    {"id": i.id, "url": i.image.url, "is_cover": i.is_cover}
                    for i in created
                ]
            },
            status=201,
        )


class OwnerPropertyImageDetail(APIView):
    permission_classes = (IsOwnerRole,)

    def get_object(self, request, pk, image_id):
        return get_object_or_404(
            PropertyImage, pk=image_id, property_id=pk, property__owner=request.user
        )

    def patch(self, request, pk, image_id):
        img = self.get_object(request, pk, image_id)
        if request.data.get("is_cover"):
            img.property.images.update(is_cover=False)
            img.is_cover = True
            img.save(update_fields=["is_cover"])
        return Response({"id": img.id, "is_cover": img.is_cover})

    def delete(self, request, pk, image_id):
        img = self.get_object(request, pk, image_id)
        prop, was_cover = img.property, img.is_cover
        img.image.delete(save=False)
        img.delete()
        if was_cover and (first := prop.images.first()):
            first.is_cover = True
            first.save(update_fields=["is_cover"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnerRoomListCreate(generics.ListCreateAPIView):
    permission_classes = (IsOwnerRole,)
    serializer_class = RoomSerializer
    pagination_class = None

    def get_property(self):
        return get_object_or_404(
            Property, pk=self.kwargs["pk"], owner=self.request.user
        )

    def get_queryset(self):
        return self.get_property().rooms.all()

    def perform_create(self, serializer):
        serializer.save(property=self.get_property())


class OwnerRoomDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsOwnerRole,)
    serializer_class = RoomSerializer
    lookup_url_kwarg = "room_id"

    def get_queryset(self):
        return Room.objects.filter(
            property_id=self.kwargs["pk"], property__owner=self.request.user
        )

    def perform_destroy(self, instance):
        from bookings.models import Booking

        if instance.bookings.filter(status__in=Booking.ACTIVE_STATUSES).exists():
            raise serializers.ValidationError(
                "This room has active bookings; deactivate it instead."
            )
        instance.delete()
