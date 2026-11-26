from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from accounts.models import User


def _has_role(request: Request, role: str) -> bool:
    # request.user is typed `AbstractBaseUser | AnonymousUser`; isinstance narrows it
    # to our User (so `.role` is known) and also rules out anonymous users.
    user = request.user
    return isinstance(user, User) and user.role == role


class IsOwnerRole(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return _has_role(request, User.Role.OWNER)


class IsRenterRole(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return _has_role(request, User.Role.RENTER)
