from django.db import models

from bookings.models import Booking


class Payment(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED, db_index=True)
    provider_order_id = models.CharField(max_length=64, unique=True)
    provider_payment_id = models.CharField(max_length=64, blank=True, db_index=True)
    provider_signature = models.CharField(max_length=128, blank=True)
    provider_refund_id = models.CharField(max_length=64, blank=True)
    method = models.CharField(max_length=30, blank=True)
    is_demo = models.BooleanField(default=False)
    error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider_order_id} ({self.status})"

    @property
    def amount_paise(self):
        return int(self.amount * 100)
