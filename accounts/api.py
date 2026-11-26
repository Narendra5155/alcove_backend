import secrets
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import otp
from .models import User
from .serializers import (
    LoginSerializer,
    OTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    RegisterSerializer,
    ResendSerializer,
)
from .tasks import send_otp_email
from .tokens import clear_tokens, issue_tokens


def _validated(serializer: BaseSerializer) -> dict[str, Any]:
    """Run validation (400 on failure) and return the validated data."""
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _start_challenge(user: User, purpose: str) -> str:
    ch = otp.create_challenge(user, purpose)
    transaction.on_commit(
        lambda: send_otp_email.delay(user.email, user.first_name, ch.code, purpose)
    )
    return ch.id


def _redirect_for(user: User) -> str:
    return "/dashboard/owner/" if user.is_owner else "/dashboard/"


class AuthAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "auth"


class RegisterView(AuthAPIView):
    def post(self, request):
        d = _validated(RegisterSerializer(data=request.data))
        with transaction.atomic():
            # allow re-registering an email that never completed verification
            User.objects.filter(email=d["email"], is_email_verified=False).delete()
            user = User.objects.create_user(
                email=d["email"],
                password=d["password"],
                full_name=d["full_name"],
                role=d["role"],
            )
            cid = _start_challenge(user, otp.PURPOSE_VERIFY_EMAIL)
        return Response(
            {
                "challenge_id": cid,
                "purpose": otp.PURPOSE_VERIFY_EMAIL,
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(AuthAPIView):
    def post(self, request):
        d = _validated(LoginSerializer(data=request.data))
        email = d["email"].lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if not user or not user.check_password(d["password"]):
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        purpose = (
            otp.PURPOSE_LOGIN if user.is_email_verified else otp.PURPOSE_VERIFY_EMAIL
        )
        with transaction.atomic():
            cid = _start_challenge(user, purpose)
        return Response({"challenge_id": cid, "purpose": purpose, "email": user.email})


class VerifyOTPView(AuthAPIView):
    throttle_scope = "otp"

    def post(self, request):
        d = _validated(OTPVerifySerializer(data=request.data))
        cid = d["challenge_id"]
        try:
            purpose = otp.get_challenge(cid)["purpose"]
            if purpose not in (otp.PURPOSE_LOGIN, otp.PURPOSE_VERIFY_EMAIL):
                raise otp.OTPError("Invalid verification request.")
            user_id = otp.verify(cid, d["code"], purpose)
        except otp.OTPError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.get(pk=user_id)
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])
        resp = Response({"redirect": _redirect_for(user), "role": user.role})
        return issue_tokens(resp, user)


class ResendOTPView(AuthAPIView):
    throttle_scope = "otp"

    def post(self, request):
        d = _validated(ResendSerializer(data=request.data))
        try:
            ch = otp.resend(d["challenge_id"])
        except otp.OTPError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.get(pk=ch.user_id)
        send_otp_email.delay(user.email, user.first_name, ch.code, ch.purpose)
        return Response({"detail": "A new code is on its way."})


class PasswordResetRequestView(AuthAPIView):
    def post(self, request):
        d = _validated(PasswordResetRequestSerializer(data=request.data))
        user = User.objects.filter(email=d["email"].lower(), is_active=True).first()
        if user:
            cid = _start_challenge(user, otp.PURPOSE_RESET)
        else:  # don't reveal whether the account exists
            cid = secrets.token_urlsafe(24)
        return Response(
            {
                "challenge_id": cid,
                "detail": "If that email is registered, a code has been sent.",
            }
        )


class PasswordResetConfirmView(AuthAPIView):
    throttle_scope = "otp"

    def post(self, request):
        d = _validated(PasswordResetConfirmSerializer(data=request.data))
        try:
            user_id = otp.verify(
                d["challenge_id"],
                d["code"],
                otp.PURPOSE_RESET,
            )
        except otp.OTPError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.get(pk=user_id)
        try:
            validate_password(d["new_password"], user)
        except ValidationError as e:
            return Response(
                {"new_password": e.messages}, status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(d["new_password"])
        user.is_email_verified = True
        user.save()
        return Response({"detail": "Password updated. You can sign in now."})


class LogoutView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        return clear_tokens(request, Response({"redirect": "/"}))


class ProfileView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(ProfileSerializer(request.user.profile).data)

    def patch(self, request):
        s = ProfileSerializer(request.user.profile, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


class RoleSwitchView(APIView):
    """Switch between travelling (RENTER) and hosting (OWNER).

    Blocked while the user has trips or guests in progress, because each role's
    pages and actions (paying, cancelling, checking guests in) depend on it.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        from bookings.models import Booking

        role = request.data.get("role")
        user = request.user
        if role not in User.Role.values:
            return Response(
                {"detail": "Choose a valid role."}, status=status.HTTP_400_BAD_REQUEST
            )
        if role == user.role:
            return Response({"role": role, "redirect": _redirect_for(user)})
        if role == User.Role.OWNER:
            if Booking.objects.filter(
                renter=user, status__in=Booking.ACTIVE_STATUSES
            ).exists():
                return Response(
                    {
                        "detail": "Finish or cancel your upcoming trips before switching to hosting."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            if Booking.objects.filter(
                property__owner=user, status__in=Booking.ACTIVE_STATUSES
            ).exists():
                return Response(
                    {
                        "detail": "You have guests booked. Complete or cancel those stays before switching to travelling."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.properties.update(
                is_active=False
            )  # hosts' listings leave search while they travel
        user.role = role
        user.save(update_fields=["role"])
        return Response({"role": role, "redirect": _redirect_for(user)})


class AvatarView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser,)

    def post(self, request):
        f = request.FILES.get("avatar")
        if not f:
            return Response(
                {"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            request.user.profile.set_avatar(f)
        except ValidationError as e:
            return Response(
                {"detail": e.messages[0]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response({"avatar_url": request.user.profile.avatar_url})

    def delete(self, request):
        p = request.user.profile
        if p.avatar:
            p.avatar.delete(save=True)
        return Response({"avatar_url": ""})
