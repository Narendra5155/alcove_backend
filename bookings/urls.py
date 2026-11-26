from django.urls import path

from . import api, views

api_urlpatterns = [
    path("bookings/", api.BookingCreateView.as_view()),
    path("bookings/mine/", api.MyBookingsView.as_view()),
    path("bookings/quote/", api.QuoteView.as_view()),
    path("bookings/<str:ref>/cancel/", api.RenterCancelView.as_view()),
    path("bookings/<str:ref>/share-location/", api.ShareLocationView.as_view()),
    path("bookings/<str:ref>/review/", api.ReviewView.as_view()),
    path("owner/bookings/<str:ref>/check-in/", api.OwnerBookingAction.as_view(op="check_in")),
    path("owner/bookings/<str:ref>/check-out/", api.OwnerBookingAction.as_view(op="check_out")),
    path("owner/bookings/<str:ref>/cancel/", api.OwnerBookingAction.as_view(op="cancel")),
]

urlpatterns = [
    path("book/<str:ref>/pay/", views.checkout_page, name="checkout"),
    path("dashboard/bookings/<str:ref>/", views.renter_booking_detail, name="renter_booking_detail"),
    path("dashboard/owner/bookings/<str:ref>/", views.owner_booking_detail, name="owner_booking_detail"),
]
