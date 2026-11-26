from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.home, name="dashboard"),
    path("dashboard/owner/", views.owner_home, name="owner_dashboard"),
    path("dashboard/owner/bookings/", views.owner_bookings, name="owner_bookings"),
    path("dashboard/owner/calendar/", views.owner_calendar, name="owner_calendar"),
    path("dashboard/owner/calendar/data/", views.owner_calendar_api, name="owner_calendar_data"),
    path("dashboard/owner/earnings/", views.owner_earnings, name="owner_earnings"),
    path("dashboard/owner/earnings.csv", views.owner_earnings_csv, name="owner_earnings_csv"),
]
