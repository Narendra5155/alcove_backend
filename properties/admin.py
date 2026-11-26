from django.contrib.gis import admin

from .models import Amenity, Property, PropertyImage, Room


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0


class ImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.GISModelAdmin):
    list_display = ["name", "city", "property_type", "owner", "is_active", "created_at"]
    list_filter = ["property_type", "city", "is_active"]
    search_fields = ["name", "city", "owner__email"]
    inlines = [RoomInline, ImageInline]
    filter_horizontal = ["amenities"]


admin.site.register(Amenity)
