from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.decorators import owner_required

from .models import Amenity, Property


@ensure_csrf_cookie
def search_page(request):
    return render(
        request,
        "properties/search.html",
        {"amenities": Amenity.objects.all(), "types": Property.Type.choices},
    )


@ensure_csrf_cookie
def property_page(request, slug):
    prop = get_object_or_404(
        Property.objects.prefetch_related("images", "amenities", "rooms").select_related("owner__profile"),
        slug=slug,
        is_active=True,
    )
    reviews = prop.reviews.select_related("renter__profile").order_by("-created_at")[:10]
    return render(request, "properties/detail.html", {"property": prop, "reviews": reviews})


@owner_required
@ensure_csrf_cookie
def owner_property_list(request):
    return render(request, "properties/owner_list.html")


@owner_required
@ensure_csrf_cookie
def owner_property_form(request, pk=None):
    prop = get_object_or_404(Property, pk=pk, owner=request.user) if pk else None
    return render(
        request,
        "properties/owner_form.html",
        {"property": prop, "amenities": Amenity.objects.all(), "types": Property.Type.choices},
    )
