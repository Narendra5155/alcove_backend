"""Issue / clear JWT cookies."""
from django.conf import settings
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


def _cookie_kwargs():
    return {
        "httponly": True,
        "secure": settings.JWT_COOKIE_SECURE,
        "samesite": settings.JWT_COOKIE_SAMESITE,
        "path": "/",
    }


def set_access_cookie(response, access: str):
    lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
    response.set_cookie(
        settings.JWT_ACCESS_COOKIE, access, max_age=int(lifetime.total_seconds()), **_cookie_kwargs()
    )


def issue_tokens(response, user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    set_access_cookie(response, str(refresh.access_token))
    lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE, str(refresh), max_age=int(lifetime.total_seconds()), **_cookie_kwargs()
    )
    return response


def clear_tokens(request, response):
    raw = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
    if raw:
        try:
            RefreshToken(raw).blacklist()
        except TokenError:
            pass
    response.delete_cookie(settings.JWT_ACCESS_COOKIE, path="/")
    response.delete_cookie(settings.JWT_REFRESH_COOKIE, path="/")
    return response
