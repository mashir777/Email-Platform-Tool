from django.core import signing

_TRACKING_SALT = "email-open-tracking-v1"


def make_open_token(queue_item_id: str) -> str:
    return signing.dumps({"q": str(queue_item_id)}, salt=_TRACKING_SALT)


def parse_open_token(token: str) -> str:
    payload = signing.loads(token, salt=_TRACKING_SALT, max_age=None)
    return str(payload["q"])
