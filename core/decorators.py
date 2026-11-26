from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.models import User


def role_required(role):
    """Require an authenticated user with the given role (OWNER / RENTER)."""

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.user.role != role:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


owner_required = role_required(User.Role.OWNER)
renter_required = role_required(User.Role.RENTER)
