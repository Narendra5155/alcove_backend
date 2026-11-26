from django.urls import path

from . import api, views

api_urlpatterns = [
    path("auth/register/", api.RegisterView.as_view()),
    path("auth/login/", api.LoginView.as_view()),
    path("auth/verify-otp/", api.VerifyOTPView.as_view()),
    path("auth/resend-otp/", api.ResendOTPView.as_view()),
    path("auth/password-reset/", api.PasswordResetRequestView.as_view()),
    path("auth/password-reset/confirm/", api.PasswordResetConfirmView.as_view()),
    path("auth/logout/", api.LogoutView.as_view()),
    path("profile/", api.ProfileView.as_view()),
    path("profile/avatar/", api.AvatarView.as_view()),
    path("profile/role/", api.RoleSwitchView.as_view()),
]

urlpatterns = [
    path("login/", views.login_page, name="login"),
    path("register/", views.register_page, name="register"),
    path("forgot-password/", views.forgot_password_page, name="forgot_password"),
    path("profile/", views.profile_page, name="profile"),
]
