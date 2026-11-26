from rest_framework import serializers

from .models import Booking, Review


class BookingCreateSerializer(serializers.Serializer):
    room_id = serializers.IntegerField()
    check_in = serializers.DateField()
    check_out = serializers.DateField()
    guests = serializers.IntegerField(min_value=1, max_value=20)
    units = serializers.IntegerField(min_value=1, max_value=10, default=1)
    special_requests = serializers.CharField(max_length=500, required=False, allow_blank=True)
    share_location = serializers.BooleanField(default=False)


class BookingSerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(source="property.name")
    property_slug = serializers.CharField(source="property.slug")
    property_city = serializers.CharField(source="property.city")
    cover_url = serializers.CharField(source="property.cover_url")
    room_name = serializers.CharField(source="room.name")
    renter_name = serializers.CharField(source="renter.full_name")
    renter_email = serializers.CharField(source="renter.email")
    status_label = serializers.CharField(source="get_status_display")
    nights = serializers.IntegerField()
    owner_payout = serializers.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        model = Booking
        fields = [
            "reference", "property_name", "property_slug", "property_city", "cover_url", "room_name",
            "renter_name", "renter_email", "check_in", "check_out", "nights", "guests", "units",
            "nightly_rate", "subtotal", "taxes", "total", "owner_payout", "status", "status_label",
            "share_location", "expires_at", "created_at",
        ]


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["rating", "comment", "created_at"]
        read_only_fields = ["created_at"]
