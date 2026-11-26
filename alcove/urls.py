from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.urls import api_urlpatterns as accounts_api
from bookings.urls import api_urlpatterns as bookings_api
from core.views import home
from notifications.urls import api_urlpatterns as notifications_api
from payments.urls import api_urlpatterns as payments_api
from properties.urls import api_urlpatterns as properties_api

api = accounts_api + properties_api + bookings_api + payments_api + notifications_api

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/", include(api)),
    path("", include("accounts.urls")),
    path("", include("properties.urls")),
    path("", include("bookings.urls")),
    path("", include("dashboard.urls")),
    path("", include("notifications.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Alcove admin"
admin.site.site_title = "Alcove"
