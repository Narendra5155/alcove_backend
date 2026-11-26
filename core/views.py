from django.shortcuts import render

from properties.models import Property


def home(request):
    featured = (
        Property.objects.filter(is_active=True)
        .prefetch_related("images")
        .order_by("-created_at")[:8]
    )
    return render(request, "core/home.html", {"featured": featured})
