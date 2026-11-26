"""Base settings for the Alcove project."""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:8000"])

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.humanize",
    # third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "channels",
    # local
    "core",
    "accounts",
    "properties",
    "bookings",
    "payments",
    "locations",
    "notifications",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.JWTCookieMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "alcove.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "alcove.wsgi.application"
ASGI_APPLICATION = "alcove.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgis://alcove:alcove@localhost:5432/alcove",
        engine="django.contrib.gis.db.backends.postgis",
    )
}
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

# Django on the host (macOS + Homebrew): point GeoDjango at GDAL/GEOS if present.
_BREW_LIB = Path("/opt/homebrew/lib")
if (_BREW_LIB / "libgdal.dylib").exists():
    GDAL_LIBRARY_PATH = env("GDAL_LIBRARY_PATH", default=str(_BREW_LIB / "libgdal.dylib"))
if (_BREW_LIB / "libgeos_c.dylib").exists():
    GEOS_LIBRARY_PATH = env("GEOS_LIBRARY_PATH", default=str(_BREW_LIB / "libgeos_c.dylib"))

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"

# OSM tile servers reject requests without a Referer; Django's default "same-origin" strips it.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Map tiles (override with a commercial provider URL for production traffic)
MAP_TILE_URL = env("MAP_TILE_URL", default="https://tile.openstreetmap.org/{z}/{x}/{y}.png")
MAP_TILE_ATTRIBUTION = env(
    "MAP_TILE_ATTRIBUTION",
    default='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
)

# ---------------------------------------------------------------- Redis
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{REDIS_URL}/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [f"{REDIS_URL}/2"]},
    }
}

# Dedicated DB for OTP challenges and live GEO positions
REDIS_APP_URL = f"{REDIS_URL}/3"

# ---------------------------------------------------------------- Celery
CELERY_BROKER_URL = f"{REDIS_URL}/0"
CELERY_RESULT_BACKEND = f"{REDIS_URL}/0"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BEAT_SCHEDULE = {
    "expire-pending-bookings": {"task": "bookings.tasks.expire_pending_bookings", "schedule": 60.0},
    "checkin-reminders": {"task": "bookings.tasks.send_checkin_reminders", "schedule": 3600.0},
    "purge-stale-positions": {"task": "locations.tasks.purge_stale_positions", "schedule": 60.0},
}

# ---------------------------------------------------------------- Email
# Brevo SMTP when BREVO_SMTP_KEY is set; otherwise generic EMAIL_* (Mailpit in docker-compose dev).
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
if env("BREVO_SMTP_KEY", default=""):
    EMAIL_HOST = env("BREVO_SMTP_SERVER", default="smtp-relay.brevo.com")
    EMAIL_PORT = env.int("BREVO_MAIL_PORT", default=587)
    EMAIL_HOST_USER = env("BREVO_LOGIN")
    EMAIL_HOST_PASSWORD = env("BREVO_SMTP_KEY")
    EMAIL_USE_SSL = EMAIL_PORT == 465
    EMAIL_USE_TLS = not EMAIL_USE_SSL
else:
    EMAIL_HOST = env("EMAIL_HOST", default=env("MAILPIT_HOST", default="localhost"))
    EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Alcove <no-reply@alcove.local>")

# ---------------------------------------------------------------- DRF / JWT
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.CookieJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_RATES": {"auth": "10/min", "otp": "10/min"},
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "SIGNING_KEY": SECRET_KEY,
}

JWT_ACCESS_COOKIE = "alcove_access"
JWT_REFRESH_COOKIE = "alcove_refresh"
JWT_COOKIE_SECURE = env.bool("JWT_COOKIE_SECURE", default=False)
JWT_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------- OTP
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN = 60

# ---------------------------------------------------------------- Razorpay
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="").strip()
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="").strip()
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="").strip()
# Without keys, simulate payments (dev only)
PAYMENTS_DEMO_FALLBACK = env.bool("PAYMENTS_DEMO_FALLBACK", default=DEBUG)

# ---------------------------------------------------------------- Bookings
BOOKING_PAYMENT_WINDOW_MINUTES = 15
PLATFORM_FEE_PERCENT = 10

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
