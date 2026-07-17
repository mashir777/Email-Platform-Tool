import json
import logging
import time
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


class ReacherError(Exception):
    pass


class ReacherUnavailableError(ReacherError):
    pass


def _backend_url() -> str:
    return getattr(settings, "REACHER_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")


def _request(*, method: str, path: str, body: dict | None = None, timeout: int = 120):
    url = f"{_backend_url()}{path}"
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    api_key = getattr(settings, "REACHER_API_KEY", "")
    if api_key:
        headers["Authorization"] = api_key

    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ReacherError(f"Reacher HTTP {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise ReacherUnavailableError(
            "Reacher email verification server is not reachable. "
            "Start it with: docker compose -f deployment/reacher-docker-compose.yml up -d"
        ) from exc


def check_email_result(email: str) -> dict:
    """Full Reacher check for any email type (Gmail, Yahoo, corporate, etc.)."""
    return _request(
        method="POST",
        path="/v0/check_email",
        body={"to_email": email},
        timeout=getattr(settings, "REACHER_REQUEST_TIMEOUT", 120),
    )


def should_keep_email_result(result: dict) -> tuple[bool, str]:
    """
    Keep every email that exists (any type: Gmail, Yahoo, company, etc.).
    Remove only emails that do not exist / have no inbox.
    """
    reachable = str(result.get("is_reachable", "unknown")).lower()
    mx = result.get("mx") if isinstance(result.get("mx"), dict) else {}
    smtp = result.get("smtp") if isinstance(result.get("smtp"), dict) else {}
    syntax = result.get("syntax") if isinstance(result.get("syntax"), dict) else {}

    if syntax and syntax.get("is_valid_syntax") is False:
        return False, "invalid"

    if reachable == "invalid":
        return False, "invalid"

    if mx and mx.get("accepts_mail") is False:
        return False, "invalid"

    # Confirmed no inbox (disabled or not deliverable), unless catch-all domain.
    if smtp and "error" not in smtp:
        if smtp.get("is_disabled"):
            return False, "invalid"
        if smtp.get("is_deliverable") is False and not smtp.get("is_catch_all"):
            return False, "invalid"

    # safe / risky / unknown — email exists or can't be proven missing: keep
    return True, reachable or "unknown"


def verify_emails(emails: list[str]) -> dict[str, dict]:
    """Verify every email individually; returns full Reacher results keyed by email."""
    unique_emails = list(dict.fromkeys(email.lower().strip() for email in emails if email))
    results: dict[str, dict] = {}
    for email in unique_emails:
        try:
            results[email] = check_email_result(email)
        except ReacherUnavailableError:
            raise
        except ReacherError as exc:
            logger.warning("Reacher check failed for %s: %s", email, exc)
            results[email] = {
                "input": email,
                "is_reachable": "unknown",
                "misc": {"is_disposable": False},
                "mx": {"accepts_mail": True},
                "smtp": {},
                "syntax": {"is_valid_syntax": True},
            }
        time.sleep(0.15)
    return results


def is_deliverable_reacher_status(status: str) -> bool:
    """Legacy helper — prefer should_keep_email_result for full checks."""
    return status in {"safe", "risky", "unknown"}
