from django.urls import path

from . import api

api_urlpatterns = [
    path("payments/order/", api.CreateOrderView.as_view()),
    path("payments/verify/", api.VerifyPaymentView.as_view()),
    path("payments/failed/", api.FailedPaymentView.as_view()),
    path("payments/webhook/", api.webhook),
]
