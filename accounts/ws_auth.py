"""Channels middleware: authenticate WebSocket connections from the JWT access cookie."""

from http.cookies import SimpleCookie

from channels.auth import UserLazyObject
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from .models import User

_jwt = JWTAuthentication()


@database_sync_to_async
def _get_user(user_id) -> User | AnonymousUser:
    return User.objects.filter(pk=user_id, is_active=True).first() or AnonymousUser()


async def _user_from_cookie(cookie_header: str) -> User | AnonymousUser:
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    morsel = cookies.get(settings.JWT_ACCESS_COOKIE)
    if not morsel:
        return AnonymousUser()
    try:
        # Validates signature, expiry and token type (SIMPLE_JWT["AUTH_TOKEN_CLASSES"]).
        token = _jwt.get_validated_token(morsel.value.encode())
    except InvalidToken:
        return AnonymousUser()
    return await _get_user(token["user_id"])


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        cookie_header = dict(scope.get("headers", [])).get(b"cookie", b"").decode()
        # Same shape as channels.auth.AuthMiddleware: scope["user"] is a lazy proxy
        # wrapping the resolved user, so consumers behave identically.
        user = UserLazyObject()
        user._wrapped = await _user_from_cookie(cookie_header)
        scope["user"] = user
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
