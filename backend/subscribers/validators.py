from subscribers.models import Subscriber

# Domains that cannot receive real email (RFC 2606 / test data).
NON_DELIVERABLE_DOMAINS = frozenset({
    "example.com",
    "example.org",
    "example.net",
    "test.com",
    "invalid",
    "localhost",
})


def is_undeliverable_email(email: str) -> bool:
    if not email or "@" not in email:
        return True
    domain = email.strip().lower().split("@")[-1]
    return domain in NON_DELIVERABLE_DOMAINS


def count_deliverable_subscribers(subscriber_list) -> int:
    """Subscribed recipients that can actually receive email."""
    count = 0
    for email in (
        subscriber_list.subscribers.filter(status=Subscriber.Status.SUBSCRIBED)
        .values_list("email", flat=True)
        .iterator()
    ):
        if not is_undeliverable_email(email):
            count += 1
    return count


def validate_subscriber_email(email: str):
    if is_undeliverable_email(email):
        from django.core.exceptions import ValidationError

        domain = email.split("@")[-1]
        raise ValidationError(
            {
                "email": [
                    f"@{domain} is a test/fake address and cannot receive mail. "
                    "Use a real Gmail or work email.",
                ],
            },
        )


def validate_csv_file(value):
    if not value:
        return

    max_size = 10 * 1024 * 1024
    if value.size > max_size:
        from django.core.exceptions import ValidationError

        raise ValidationError("CSV file must not exceed 10 MB.")

    name = value.name.lower()
    if not name.endswith(".csv"):
        from django.core.exceptions import ValidationError

        raise ValidationError("Only CSV files are allowed.")
