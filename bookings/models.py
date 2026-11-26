import builtins
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from properties.models import Property, Room


def make_reference():
    return "ALC" + secrets.token_hex(4).upper()


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Awaiting payment"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CHECKED_IN = "CHECKED_IN", "Checked in"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    ACTIVE_STATUSES = (Status.PENDING, Status.CONFIRMED, Status.CHECKED_IN)

    TAX_RATE = Decimal("0.12")

    reference = models.CharField(max_length=12, unique=True, default=make_reference, editable=False)
    renter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="bookings")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings")
    check_in = models.DateField()
    check_out = models.DateField()
    guests = models.PositiveSmallIntegerField(default=1)
    units = models.PositiveSmallIntegerField(default=1)
    nightly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    taxes = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    special_requests = models.TextField(blank=True, max_length=500)
    share_location = models.BooleanField(default=False, help_text="Renter shares live location with host on arrival day")
    expires_at = models.DateTimeField(null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["room", "check_in", "check_out"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(check_out__gt=models.F("check_in")), name="booking_dates_valid")
        ]

    def __str__(self):
        return self.reference

    @builtins.property
    def nights(self):
        return (self.check_out - self.check_in).days

    @builtins.property
    def owner(self):
        return self.property.owner

    @builtins.property
    def is_arrival_day(self):
        return self.status == self.Status.CONFIRMED and self.check_in == timezone.localdate()

    @builtins.property
    def platform_fee(self):
        return (self.subtotal * Decimal(settings.PLATFORM_FEE_PERCENT) / 100).quantize(Decimal("0.01"))

    @builtins.property
    def owner_payout(self):
        return self.subtotal - self.platform_fee

    @builtins.property
    def status_color(self):
        return {
            "PENDING": "amber",
            "CONFIRMED": "emerald",
            "CHECKED_IN": "sky",
            "COMPLETED": "slate",
            "CANCELLED": "rose",
            "EXPIRED": "zinc",
        }[self.status]


class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="review")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="reviews")
    renter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
