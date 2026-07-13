import re
import secrets

import dns.exception
import dns.resolver
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.encryption import encrypt_value
from domains.models import SendingDomain

DOMAIN_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$",
)


def normalize_domain(domain: str) -> str:
    return domain.strip().lower().removeprefix("http://").removeprefix("https://").rstrip("/")


def validate_domain_format(domain: str):
    if not DOMAIN_PATTERN.match(domain):
        raise ValidationError({"domain": ["Enter a valid domain name (e.g. example.com)."]})


def get_owner_domains(user):
    return SendingDomain.objects.filter(owner=user)


def _clear_default_flag(owner, exclude_id=None):
    qs = SendingDomain.objects.filter(owner=owner, is_default=True)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    qs.update(is_default=False)


def _generate_dkim_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    public_key_body = "".join(
        line for line in public_key.splitlines() if not line.startswith("-----")
    )
    return private_pem, public_key_body


def _dns_host_label(full_host: str, domain: str) -> str:
    if full_host == domain:
        return "@"
    suffix = f".{domain}"
    if full_host.endswith(suffix):
        return full_host[: -len(suffix)]
    return full_host


def build_dns_records(domain_obj: SendingDomain) -> list[dict]:
    ownership_host = f"_emailplatform-verify.{domain_obj.domain}"
    dkim_host = f"{domain_obj.dkim_selector}._domainkey.{domain_obj.domain}"
    dmarc_host = f"_dmarc.{domain_obj.domain}"

    spf_value = "v=spf1 a mx ~all"
    spf_note = "Add only if you do not already have an SPF record at your domain root."
    if domain_obj.spf_verified:
        spf_note = "Your domain already has a valid SPF record. No changes needed."

    dmarc_value = f"v=DMARC1; p=none; rua=mailto:dmarc@{domain_obj.domain}"
    dmarc_note = "Add only if you do not already have a DMARC record."
    if domain_obj.dmarc_verified:
        dmarc_note = "Your domain already has a valid DMARC record. No changes needed."

    return [
        {
            "type": "TXT",
            "purpose": "ownership",
            "host": ownership_host,
            "host_label": _dns_host_label(ownership_host, domain_obj.domain),
            "value": f"emailplatform-verify={domain_obj.verification_token}",
            "verified": domain_obj.status == SendingDomain.Status.VERIFIED,
            "required": True,
            "note": "Required. In cPanel/Namecheap use the Host label shown below.",
        },
        {
            "type": "TXT",
            "purpose": "spf",
            "host": domain_obj.domain,
            "host_label": "@",
            "value": spf_value,
            "verified": domain_obj.spf_verified,
            "required": False,
            "note": spf_note,
        },
        {
            "type": "TXT",
            "purpose": "dkim",
            "host": dkim_host,
            "host_label": _dns_host_label(dkim_host, domain_obj.domain),
            "value": (
                f"v=DKIM1; k=rsa; p={domain_obj.dkim_public_key}"
                if domain_obj.dkim_public_key
                else ""
            ),
            "verified": domain_obj.dkim_verified,
            "required": True,
            "note": "Required for signed outbound mail. Paste the full value as one line.",
        },
        {
            "type": "TXT",
            "purpose": "dmarc",
            "host": dmarc_host,
            "host_label": _dns_host_label(dmarc_host, domain_obj.domain),
            "value": dmarc_value,
            "verified": domain_obj.dmarc_verified,
            "required": False,
            "note": dmarc_note,
        },
    ]


@transaction.atomic
def create_sending_domain(*, owner, **fields):
    domain = normalize_domain(fields.pop("domain"))
    validate_domain_format(domain)

    if SendingDomain.objects.filter(owner=owner, domain=domain).exists():
        raise ValidationError({"domain": ["This domain is already added."]})

    if fields.get("is_default"):
        _clear_default_flag(owner)

    private_pem, public_body = _generate_dkim_keys()
    token = secrets.token_urlsafe(24)

    return SendingDomain.objects.create(
        owner=owner,
        domain=domain,
        verification_token=token,
        dkim_public_key=public_body,
        dkim_private_key_encrypted=encrypt_value(private_pem),
        **fields,
    )


@transaction.atomic
def update_sending_domain(*, sending_domain, **validated_data):
    if validated_data.get("is_default"):
        _clear_default_flag(sending_domain.owner, exclude_id=sending_domain.id)

    for field, value in validated_data.items():
        setattr(sending_domain, field, value)
    sending_domain.save()
    return sending_domain


@transaction.atomic
def delete_sending_domain(*, sending_domain):
    sending_domain.delete()


@transaction.atomic
def set_default_sending_domain(*, sending_domain):
    if not sending_domain.is_active:
        raise ValidationError({"is_active": ["Inactive domain cannot be set as default."]})
    if sending_domain.status != SendingDomain.Status.VERIFIED:
        raise ValidationError({"status": ["Only verified domains can be set as default."]})
    _clear_default_flag(sending_domain.owner, exclude_id=sending_domain.id)
    sending_domain.is_default = True
    sending_domain.save()
    return sending_domain


def _txt_records(host: str) -> list[str]:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 10
    try:
        answers = resolver.resolve(host, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
        return []
    except dns.resolver.NoNameservers:
        return []

    records = []
    for answer in answers:
        parts = []
        for string in answer.strings:
            parts.append(string.decode("utf-8", errors="ignore"))
        records.append("".join(parts))
    return records


def _ownership_verified(*, domain: str, token: str) -> bool:
    expected = f"emailplatform-verify={token}"
    ownership_host = f"_emailplatform-verify.{domain}"
    candidates = _txt_records(ownership_host) + _txt_records(domain)
    return any(expected in record for record in candidates)


def verify_sending_domain(*, sending_domain):
    ownership_ok = _ownership_verified(
        domain=sending_domain.domain,
        token=sending_domain.verification_token,
    )

    spf_records = _txt_records(sending_domain.domain)
    spf_ok = any("v=spf1" in record.lower() for record in spf_records)

    dkim_host = f"{sending_domain.dkim_selector}._domainkey.{sending_domain.domain}"
    dkim_records = _txt_records(dkim_host)
    dkim_ok = any(
        sending_domain.dkim_public_key and sending_domain.dkim_public_key in record
        for record in dkim_records
    )

    dmarc_records = _txt_records(f"_dmarc.{sending_domain.domain}")
    dmarc_ok = any("v=dmarc1" in record.lower() for record in dmarc_records)

    relaxed = getattr(settings, "DOMAIN_RELAXED_VERIFICATION", False)
    if not ownership_ok and relaxed and spf_ok:
        ownership_ok = True

    sending_domain.spf_verified = spf_ok
    sending_domain.dkim_verified = dkim_ok
    sending_domain.dmarc_verified = dmarc_ok
    sending_domain.last_verified_at = timezone.now()

    if ownership_ok:
        sending_domain.status = SendingDomain.Status.VERIFIED
        sending_domain.is_active = True
        if not SendingDomain.objects.filter(
            owner=sending_domain.owner,
            is_default=True,
        ).exists():
            sending_domain.is_default = True

        if spf_ok and dkim_ok and dmarc_ok:
            sending_domain.last_verification_message = "All DNS records verified."
        elif dkim_ok:
            sending_domain.last_verification_message = "Domain verified. DKIM is active."
        elif relaxed and spf_ok and not dkim_ok:
            sending_domain.last_verification_message = (
                "Domain verified (SPF found). Add Ownership + DKIM TXT for production deliverability."
            )
        elif spf_ok or dmarc_ok:
            sending_domain.last_verification_message = (
                "Ownership verified. Add the DKIM record for signed outbound mail."
            )
        else:
            sending_domain.last_verification_message = (
                "Domain ownership verified. Add DKIM (and SPF if missing) for deliverability."
            )
        success = True
    else:
        sending_domain.status = SendingDomain.Status.FAILED
        missing = ["Ownership TXT (_emailplatform-verify)"]
        if not dkim_ok:
            missing.append("DKIM TXT")
        sending_domain.last_verification_message = (
            f"{' and '.join(missing)} not found. "
            "Add the DNS records below, wait 5–30 minutes, then click Verify again."
        )
        success = False

    sending_domain.save()
    return success, sending_domain.last_verification_message


def get_domain_stats(user):
    qs = get_owner_domains(user)
    return {
        "total": qs.count(),
        "verified": qs.filter(status=SendingDomain.Status.VERIFIED).count(),
        "pending": qs.filter(status=SendingDomain.Status.PENDING).count(),
        "failed": qs.filter(status=SendingDomain.Status.FAILED).count(),
        "default_configured": qs.filter(is_default=True).exists(),
    }
