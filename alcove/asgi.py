"""ASGI entrypoint: HTTP via Django, WebSockets via Channels."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alcove.settings.dev")
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from accounts.ws_auth import JWTAuthMiddlewareStack
from locations.routing import websocket_urlpatterns as location_ws
from notifications.routing import websocket_urlpatterns as notification_ws

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddlewareStack(URLRouter(notification_ws + location_ws))
        ),
    }
)
