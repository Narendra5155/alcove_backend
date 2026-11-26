"""DRF authentication reading the JWT from an HttpOnly cookie (with CSRF enforcement)."""
from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:  # Bearer header (API clients)
            return super().authenticate(request)

        raw = request.COOKIES.get(settings.JWT_ACCESS_COOKIE)
        if not raw:
            return None
        try:
            validated = self.get_validated_token(raw)
        except exceptions.AuthenticationFailed:
            return None  # treat as anonymous; middleware handles refresh
        user = self.get_user(validated)
        self._enforce_csrf(request)
        return user, validated

    def _enforce_csrf(self, request):
        def dummy_get_response(_):  # pragma: no cover
            return None

        check = CSRFCheck(dummy_get_response)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")
