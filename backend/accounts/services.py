import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserRole, UserToken
from accounts.tasks import send_password_reset_email, send_verification_email


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def _create_user_token(user, token_type, lifetime_hours):
    raw_token = _generate_raw_token()
    UserToken.objects.filter(
        user=user,
        token_type=token_type,
        is_used=False,
    ).update(is_used=True)
    user_token = UserToken.objects.create(
        user=user,
        token_hash=_hash_token(raw_token),
        token_type=token_type,
        expires_at=timezone.now() + timedelta(hours=lifetime_hours),
    )
    return raw_token, user_token


def _get_valid_token(raw_token, token_type):
    try:
        user_token = UserToken.objects.select_related("user").get(
            token_hash=_hash_token(raw_token),
            token_type=token_type,
            is_used=False,
        )
    except UserToken.DoesNotExist:
        return None
    if not user_token.is_valid:
        return None
    return user_token


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@transaction.atomic
def register_user(*, email, password, **extra_fields):
    email = email.lower().strip()
    if User.objects.filter(email=email).exists():
        raise ValidationError({"email": ["A user with this email already exists."]})

    validate_password(password)

    username = extra_fields.pop("username", None) or email.split("@")[0]
    base_username = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    user = User.objects.create_user(
        email=email,
        password=password,
        username=username,
        role=UserRole.CLIENT,
        **extra_fields,
    )

    raw_token, _ = _create_user_token(
        user,
        UserToken.TokenType.EMAIL_VERIFICATION,
        lifetime_hours=settings.EMAIL_VERIFICATION_TOKEN_HOURS,
    )
    # Email is sent after the DB commit (see register_user_and_notify).
    return user, raw_token


def register_user_and_notify(*, email, password, **extra_fields):
    user, raw_token = register_user(email=email, password=password, **extra_fields)
    try:
        send_verification_email.delay(str(user.id), raw_token)
    except Exception:
        # Signup must succeed even if SMTP/Celery fails (e.g. on Vercel).
        import logging

        logging.getLogger(__name__).exception(
            "Failed to queue verification email for user_id=%s", user.id
        )
    return user


def authenticate_user(*, email, password):
    email = email.lower().strip()
    user = authenticate(
        request=None,
        username=email,
        password=password,
    )
    if user is None:
        raise ValidationError({"detail": ["Invalid email or password."]})
    if not user.is_active:
        raise ValidationError({"detail": ["This account has been deactivated."]})
    return user


def logout_user(*, refresh_token):
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
    except Exception as exc:
        raise ValidationError({"refresh": ["Invalid or expired refresh token."]}) from exc


def request_password_reset(*, email):
    email = email.lower().strip()
    try:
        user = User.objects.get(email=email, is_active=True)
    except User.DoesNotExist:
        return

    raw_token, _ = _create_user_token(
        user,
        UserToken.TokenType.PASSWORD_RESET,
        lifetime_hours=settings.PASSWORD_RESET_TOKEN_HOURS,
    )
    send_password_reset_email.delay(str(user.id), raw_token)


@transaction.atomic
def reset_password(*, token, new_password):
    user_token = _get_valid_token(token, UserToken.TokenType.PASSWORD_RESET)
    if user_token is None:
        raise ValidationError({"token": ["Invalid or expired password reset token."]})

    validate_password(new_password, user=user_token.user)
    user = user_token.user
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    user_token.is_used = True
    user_token.save(update_fields=["is_used"])


@transaction.atomic
def change_password(*, user, old_password, new_password):
    if not user.check_password(old_password):
        raise ValidationError({"old_password": ["Current password is incorrect."]})
    validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])


@transaction.atomic
def verify_email(*, token):
    user_token = _get_valid_token(token, UserToken.TokenType.EMAIL_VERIFICATION)
    if user_token is None:
        raise ValidationError({"token": ["Invalid or expired verification token."]})

    user = user_token.user
    user.is_verified = True
    user.save(update_fields=["is_verified", "updated_at"])
    user_token.is_used = True
    user_token.save(update_fields=["is_used"])
    return user


def resend_verification_email(*, user):
    if user.is_verified:
        raise ValidationError({"detail": ["Email is already verified."]})

    raw_token, _ = _create_user_token(
        user,
        UserToken.TokenType.EMAIL_VERIFICATION,
        lifetime_hours=settings.EMAIL_VERIFICATION_TOKEN_HOURS,
    )
    send_verification_email.delay(str(user.id), raw_token)


@transaction.atomic
def update_user_profile(*, user, **validated_data):
    for field, value in validated_data.items():
        setattr(user, field, value)
    user.save()
    return user


@transaction.atomic
def upload_user_avatar(*, user, avatar_file):
    if user.avatar:
        user.avatar.delete(save=False)
    user.avatar = avatar_file
    user.save(update_fields=["avatar", "updated_at"])
    return user
