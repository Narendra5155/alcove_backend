from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def login_page(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/owner/" if request.user.is_owner else "/dashboard/")
    return render(request, "accounts/login.html")


@ensure_csrf_cookie
def register_page(request):
    if request.user.is_authenticated:
        return redirect("/")
    return render(request, "accounts/register.html", {"role": request.GET.get("role", "RENTER").upper()})


@ensure_csrf_cookie
def forgot_password_page(request):
    return render(request, "accounts/forgot_password.html")


@login_required
@ensure_csrf_cookie
def profile_page(request):
    return render(request, "accounts/profile.html")
