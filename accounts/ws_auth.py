"""Channels middleware: authenticate WebSocket connections from the JWT access cookie."""
from http.cookies import SimpleCookie

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _get_user(user_id):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(pk=user_id, is_active=True).first() or AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope["user"] = AnonymousUser()
        cookie_header = dict(scope.get("headers", [])).get(b"cookie", b"").decode()
        cookies = SimpleCookie()
        cookies.load(cookie_header)
        morsel = cookies.get(settings.JWT_ACCESS_COOKIE)
        if morsel:
            try:
                token = AccessToken(morsel.value)
                scope["user"] = await _get_user(token["user_id"])
            except TokenError:
                pass
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):  # noqa: N802
    return JWTAuthMiddleware(inner)
