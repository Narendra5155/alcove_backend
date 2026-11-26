from django.conf import settings


def site(request):
    return {
        "SITE_NAME": "Alcove",
        "MAP_TILE_URL": settings.MAP_TILE_URL,
        "MAP_TILE_ATTRIBUTION": settings.MAP_TILE_ATTRIBUTION,
        "RAZORPAY_TEST_MODE": settings.RAZORPAY_KEY_ID.startswith("rzp_test") or not settings.RAZORPAY_KEY_ID,
    }
