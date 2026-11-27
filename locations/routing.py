from django.urls import path

from .consumers import LocationConsumer

websocket_urlpatterns = [
    # django-stubs types path() for HTTP views only; Channels routes ASGI apps with it.
    path("ws/location/", LocationConsumer.as_asgi()),  # pyright: ignore[reportCallIssue, reportArgumentType]
]
