import logging

import requests

logger = logging.getLogger()

DISCORD_API_BASE = "https://discord.com/api/v10"


def send_followup(application_id: str, interaction_token: str, content: str, *, allowed_mentions: dict = None, flags: int = 0) -> None:
    """POST a followup message to the Discord interaction webhook.

    Authenticated by the interaction token in the URL — no bot token needed.
    Discord accepts followups for 15 minutes after the original interaction.
    """
    url = f"{DISCORD_API_BASE}/webhooks/{application_id}/{interaction_token}"
    payload = {"content": content}
    if allowed_mentions is not None:
        payload["allowed_mentions"] = allowed_mentions
    if flags:
        payload["flags"] = flags
    resp = requests.post(url, json=payload, timeout=10)
    if resp.ok:
        logger.info(f"[followup] followup sent OK status={resp.status_code}")
    else:
        # Body only — never log the URL, it embeds the interaction token.
        logger.error(f"[followup] followup failed status={resp.status_code} body={resp.text}")
