from django.urls import path

from .consumers import NotificationConsumer

websocket_urlpatterns = [
    # django-stubs types path() for HTTP views only; Channels routes ASGI apps with it.
    path("ws/notifications/", NotificationConsumer.as_asgi()),  # pyright: ignore[reportCallIssue, reportArgumentType]
]
