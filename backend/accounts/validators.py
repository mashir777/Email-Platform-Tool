import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

PHONE_ALLOWED_CHARS = re.compile(r"^[\d\s\-()+.]+$")


def validate_phone_number(value):
    if not value:
        return

    cleaned = value.strip()
    if not PHONE_ALLOWED_CHARS.match(cleaned):
        raise ValidationError(_("Enter a valid phone number."))

    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 7 or len(digits) > 15:
        raise ValidationError(_("Phone number must contain 7 to 15 digits."))


def validate_avatar_file(value):
    if not value:
        return

    max_size = 5 * 1024 * 1024
    if value.size > max_size:
        raise ValidationError(_("Avatar file size must not exceed 5 MB."))

    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    content_type = getattr(value, "content_type", None)
    if content_type and content_type not in allowed_types:
        raise ValidationError(_("Avatar must be a JPEG, PNG, WebP, or GIF image."))

    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    extension = "." + value.name.rsplit(".", 1)[-1].lower()
    if extension not in allowed_extensions:
        raise ValidationError(_("Avatar file extension is not allowed."))
