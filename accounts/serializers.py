from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Profile

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.Role.choices)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value, is_email_verified=True).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        validate_password(attrs["password"], User(email=attrs["email"], full_name=attrs["full_name"]))
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class OTPVerifySerializer(serializers.Serializer):
    challenge_id = serializers.CharField()
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code."})


class ResendSerializer(serializers.Serializer):
    challenge_id = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(OTPVerifySerializer):
    new_password = serializers.CharField(write_only=True)


class ProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", max_length=150)
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    avatar_url = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = ["full_name", "email", "role", "avatar_url", "phone", "bio", "city", "business_name", "gstin"]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        if "full_name" in user_data:
            instance.user.full_name = user_data["full_name"]
            instance.user.save(update_fields=["full_name"])
        return super().update(instance, validated_data)
