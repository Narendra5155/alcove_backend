"""ASGI entrypoint: HTTP via Django, WebSockets via Channels."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alcove.settings.dev")
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from accounts.ws_auth import JWTAuthMiddlewareStack  # noqa: E402
from locations.routing import websocket_urlpatterns as location_ws  # noqa: E402
from notifications.routing import websocket_urlpatterns as notification_ws  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddlewareStack(URLRouter(notification_ws + location_ws))
        ),
    }
)
