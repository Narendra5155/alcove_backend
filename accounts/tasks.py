from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

SUBJECTS = {
    "login": "Your Alcove sign-in code",
    "verify_email": "Verify your Alcove email",
    "reset_password": "Reset your Alcove password",
}


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_otp_email(email, name, code, purpose):
    ctx = {"name": name, "code": code, "purpose": purpose}
    send_mail(
        subject=SUBJECTS.get(purpose, "Your Alcove code"),
        message=render_to_string("emails/otp.txt", ctx),
        html_message=render_to_string("emails/otp.html", ctx),
        from_email=None,
        recipient_list=[email],
    )
