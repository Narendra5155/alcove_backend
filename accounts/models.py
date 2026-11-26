from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from core.images import resize_image, validate_image


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, is_email_verified=True, role=User.Role.OWNER)
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        RENTER = "RENTER", "Renter"
        OWNER = "OWNER", "Owner"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.RENTER)
    is_email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    def __str__(self):
        return self.email

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def is_renter(self):
        return self.role == self.Role.RENTER

    @property
    def first_name(self):
        return (self.full_name or self.email).split(" ")[0]

    @property
    def initials(self):
        parts = (self.full_name or self.email).split()
        return "".join(p[0] for p in parts[:2]).upper()


def avatar_path(instance, filename):
    return f"avatars/{instance.user_id}/{timezone.now():%Y%m%d%H%M%S}.jpg"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to=avatar_path, blank=True, validators=[validate_image])
    phone = models.CharField(max_length=20, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    city = models.CharField(max_length=80, blank=True)
    # Owner-only details
    business_name = models.CharField(max_length=150, blank=True)
    gstin = models.CharField("GSTIN", max_length=15, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile<{self.user.email}>"

    def set_avatar(self, uploaded):
        validate_image(uploaded)
        if self.avatar:
            self.avatar.delete(save=False)
        self.avatar.save("avatar.jpg", resize_image(uploaded, (400, 400), crop=True), save=True)

    @property
    def avatar_url(self):
        return self.avatar.url if self.avatar else ""
