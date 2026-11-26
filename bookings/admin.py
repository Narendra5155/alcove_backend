from django.contrib import admin

from .models import Booking, Review


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["reference", "property", "room", "renter", "check_in", "check_out", "total", "status"]
    list_filter = ["status", "check_in"]
    search_fields = ["reference", "renter__email", "property__name"]
    raw_id_fields = ["renter", "property", "room"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["property", "renter", "rating", "created_at"]
