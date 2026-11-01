from datetime import datetime

def get_user_ping(user_id: str) -> str:
    return f"<@{user_id}>"

def get_channel_mention(channel_id: str) -> str:
    return f"<#{channel_id}>"

def get_role_ping(role_id: str) -> str:
    return f"<@&{role_id}>"

def get_discord_timestamp(utc_iso: str, style: str = "F") -> str | None:
    """
    Converts a UTC ISO-8601 string into a Discord timestamp tag (e.g. <t:1700000000:F>)
    that Discord renders in each viewer's local timezone.
    Returns None if the input cannot be parsed.
    """
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return f"<t:{int(dt.timestamp())}:{style}>"
    except (ValueError, AttributeError, TypeError):
        return None
