from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["provider_order_id", "booking", "amount", "status", "is_demo", "created_at", "paid_at"]
    list_filter = ["status", "is_demo"]
    search_fields = ["provider_order_id", "provider_payment_id", "booking__reference"]
    readonly_fields = [f.name for f in Payment._meta.fields]
