from django.contrib.gis.geos import Point
from rest_framework import serializers

from .models import Amenity, Property, PropertyImage, Room


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ("id", "name", "icon")


class PropertyImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyImage
        fields = ("id", "url", "caption", "is_cover", "order")

    def get_url(self, obj):
        return obj.image.url


class RoomSerializer(serializers.ModelSerializer):
    available = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Room
        fields = (
            "id",
            "name",
            "description",
            "price_per_night",
            "max_guests",
            "beds",
            "quantity",
            "is_active",
            "available",
        )

    def validate_price_per_night(self, v):
        if v <= 0:
            raise serializers.ValidationError("Price must be positive.")
        return v


class PropertyCardSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(read_only=True)
    lng = serializers.FloatField(read_only=True)
    cover_url = serializers.CharField(read_only=True)
    starting_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True, default=0)
    distance_km = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    type_label = serializers.CharField(
        source="get_property_type_display", read_only=True
    )

    class Meta:
        model = Property
        fields = (
            "id",
            "slug",
            "name",
            "property_type",
            "type_label",
            "city",
            "address",
            "lat",
            "lng",
            "cover_url",
            "starting_price",
            "rating",
            "review_count",
            "distance_km",
            "url",
        )

    def get_distance_km(self, obj):
        d = getattr(obj, "distance", None)
        return round(d.km, 2) if d is not None else None

    def get_url(self, obj):
        return f"/stays/{obj.slug}/"


class PropertyDetailSerializer(PropertyCardSerializer):
    images = PropertyImageSerializer(many=True, read_only=True)
    rooms = serializers.SerializerMethodField()
    amenities = AmenitySerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)

    class Meta(PropertyCardSerializer.Meta):
        fields = PropertyCardSerializer.Meta.fields + (
            "description",
            "state",
            "pincode",
            "check_in_time",
            "check_out_time",
            "house_rules",
            "images",
            "rooms",
            "amenities",
            "owner_name",
        )

    def get_rooms(self, obj):
        return RoomSerializer(obj.rooms.filter(is_active=True), many=True).data


class OwnerPropertySerializer(serializers.ModelSerializer):
    """Create/update a property as its owner. Location given as lat/lng."""

    lat = serializers.FloatField(write_only=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(write_only=True, min_value=-180, max_value=180)
    amenity_ids = serializers.PrimaryKeyRelatedField(
        source="amenities", queryset=Amenity.objects.all(), many=True, required=False
    )
    images = PropertyImageSerializer(many=True, read_only=True)
    rooms = RoomSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = (
            "id",
            "slug",
            "name",
            "property_type",
            "description",
            "address",
            "city",
            "state",
            "pincode",
            "lat",
            "lng",
            "amenity_ids",
            "check_in_time",
            "check_out_time",
            "house_rules",
            "is_active",
            "images",
            "rooms",
        )
        read_only_fields = ("slug",)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["lat"], data["lng"] = instance.lat, instance.lng
        return data

    def _apply_location(self, validated):
        lat, lng = validated.pop("lat", None), validated.pop("lng", None)
        if lat is not None and lng is not None:
            validated["location"] = Point(lng, lat, srid=4326)
        return validated

    def create(self, validated):
        validated = self._apply_location(validated)
        if "location" not in validated:
            raise serializers.ValidationError({"lat": "Pick the location on the map."})
        return super().create(validated)

    def update(self, instance, validated):
        return super().update(instance, self._apply_location(validated))
