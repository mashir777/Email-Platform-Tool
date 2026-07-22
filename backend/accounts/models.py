import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


def avatar_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"avatars/{instance.id}/{uuid.uuid4().hex}.{ext}"


class UserRole(models.TextChoices):
    SUPER_ADMIN = "super_admin", _("Super Admin")
    ADMIN = "admin", _("Admin")
    MANAGER = "manager", _("Manager")
    CLIENT = "client", _("Client")


class User(AbstractUser):
    """Custom user model for the email marketing platform."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    email = models.EmailField(
        _("email address"),
        unique=True,
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CLIENT,
        db_index=True,
    )
    phone = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=63, default="UTC")
    # Shared Reply-To for all sends (20–200 senders → one inbox). Empty = use From.
    default_reply_to = models.EmailField(
        blank=True,
        help_text=_("Shared inbox for replies. Overrides per-SMTP Reply-To when set."),
    )
    avatar = models.ImageField(
        upload_to=avatar_upload_path,
        blank=True,
        null=True,
    )
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["role"]),
            models.Index(fields=["is_active", "is_verified"]),
        ]

    def __str__(self):
        return self.email

    @property
    def is_super_admin(self):
        return self.role == UserRole.SUPER_ADMIN or self.is_superuser

    @property
    def is_admin(self):
        return self.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN} or self.is_superuser

    @property
    def is_manager(self):
        return self.role in {
            UserRole.SUPER_ADMIN,
            UserRole.ADMIN,
            UserRole.MANAGER,
        } or self.is_superuser


class UserToken(models.Model):
    """Secure token storage for email verification and password reset."""

    class TokenType(models.TextChoices):
        EMAIL_VERIFICATION = "email_verification", _("Email Verification")
        PASSWORD_RESET = "password_reset", _("Password Reset")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tokens",
    )
    token_hash = models.CharField(max_length=128, unique=True, db_index=True)
    token_type = models.CharField(max_length=30, choices=TokenType.choices)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token_type", "is_used"]),
            models.Index(fields=["user", "token_type"]),
        ]

    def __str__(self):
        return f"{self.token_type} token for {self.user.email}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired
