"""Authenticate template views from the JWT cookie, refreshing the access token transparently."""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .tokens import set_access_cookie

log = logging.getLogger(__name__)
User = get_user_model()


def _user_from_access(raw):
    token = AccessToken(raw)
    return User.objects.filter(pk=token["user_id"], is_active=True).first()


class JWTCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        new_access = None
        access = request.COOKIES.get(settings.JWT_ACCESS_COOKIE)
        user = None
        if access:
            try:
                user = _user_from_access(access)
            except TokenError:
                user = None
        if user is None:
            refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
            if refresh:
                try:
                    rt = RefreshToken(refresh)
                    rt.check_blacklist()
                    new_access = str(rt.access_token)
                    user = _user_from_access(new_access)
                    # let DRF's cookie authenticator see the fresh token in this request
                    request.COOKIES[settings.JWT_ACCESS_COOKIE] = new_access
                except TokenError:
                    user = None
        if user is not None:
            request.user = user
            request._cached_user = user

        response = self.get_response(request)
        if new_access and user is not None:
            set_access_cookie(response, new_access)
        return response
