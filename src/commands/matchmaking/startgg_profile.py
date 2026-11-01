import re

# MIRROR: jobs/deferred_worker/worker_startgg_api.py parse_profile_slug — keep in sync
# (independent Lambda packaging prevents imports).
_PROFILE_URL_PATTERN = re.compile(r"start\.gg/user/([A-Za-z0-9_-]+)", re.IGNORECASE)
_PROFILE_SLUG_PATTERN = re.compile(r"(?:user/)?([A-Za-z0-9_-]+)/?")


def parse_profile_slug(value: str) -> str | None:
    """Normalize a start.gg profile URL, 'user/<id>' slug or bare '<id>' to
    'user/<id>'. Returns None if it isn't recognizable as a profile."""
    text = (value or "").strip()
    match = _PROFILE_URL_PATTERN.search(text) or _PROFILE_SLUG_PATTERN.fullmatch(text)
    return f"user/{match.group(1)}" if match else None
