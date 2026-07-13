from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


def _build_verification_message(user, verify_url):
    return (
        f"Hello {user.first_name or user.email},\n\n"
        f"Please verify your email address by visiting the link below:\n\n"
        f"{verify_url}\n\n"
        f"This link expires in {settings.EMAIL_VERIFICATION_TOKEN_HOURS} hours.\n\n"
        f"If you did not create an account, you can safely ignore this email.\n\n"
        f"— Email Platform Team"
    )


def _build_password_reset_message(user, reset_url):
    return (
        f"Hello {user.first_name or user.email},\n\n"
        f"We received a request to reset your password. "
        f"Visit the link below to set a new password:\n\n"
        f"{reset_url}\n\n"
        f"This link expires in {settings.PASSWORD_RESET_TOKEN_HOURS} hours.\n\n"
        f"If you did not request a password reset, you can safely ignore this email.\n\n"
        f"— Email Platform Team"
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email(self, user_id, raw_token):
    from accounts.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    send_mail(
        subject="Verify your Email Platform account",
        message=_build_verification_message(user, verify_url),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_id, raw_token):
    from accounts.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    send_mail(
        subject="Reset your Email Platform password",
        message=_build_password_reset_message(user, reset_url),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
