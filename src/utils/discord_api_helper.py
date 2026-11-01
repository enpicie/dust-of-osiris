"""Calls to the Discord REST API made with the bot token.

Only needed when the bot acts on Discord outside the interaction reply itself —
assigning roles, posting to another channel, reading guild info. Replying to a
slash command (and deferred followups) does NOT need the bot token.

The token lives in Secrets Manager and is fetched once per warm container;
Terraform passes only the secret's name (DISCORD_BOT_TOKEN_SECRET_NAME).
"""
from typing import Optional

import boto3
import requests

import constants

DISCORD_API_BASE_URL = "https://discord.com/api/v10"

_secretsmanager_client = None
_bot_token: str | None = None


def _get_bot_token() -> str:
    """Fetches the Discord bot token from Secrets Manager, caching it for the lifetime of the warm Lambda."""
    global _secretsmanager_client, _bot_token
    if _bot_token is None:
        if _secretsmanager_client is None:
            _secretsmanager_client = boto3.client("secretsmanager", region_name=constants.AWS_REGION)
        response = _secretsmanager_client.get_secret_value(SecretId=constants.DISCORD_BOT_TOKEN_SECRET_NAME)
        _bot_token = response["SecretString"]
    return _bot_token


def _bot_auth_headers() -> dict:
    return {
        "Authorization": f"Bot {_get_bot_token()}",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, json: dict | None = None, log_suffix: str = "") -> requests.Response:
    """Execute a Discord API request against DISCORD_API_BASE_URL and return the raw Response."""
    print(f"[discord] {method} {path}{log_suffix}")
    # Timeout stays under Discord's 3s interaction deadline budget.
    return requests.request(method, f"{DISCORD_API_BASE_URL}{path}", headers=_bot_auth_headers(), json=json, timeout=2)


def _extract_discord_error(response: requests.Response) -> str:
    """Pull a human-readable message out of a Discord error response, preferring
    the first field-level message over the generic top-level "Invalid Form Body"."""
    try:
        body = response.json()
        for field_errors in body.get("errors", {}).values():
            for err in field_errors.get("_errors", []):
                if "message" in err:
                    return err["message"]
        return body.get("message", "Unknown Discord API error")
    except Exception:
        return f"HTTP {response.status_code}"


def get_guild_name(guild_id: str) -> Optional[str]:
    """Fetch a guild's display name. Returns the name string on success, None on any error."""
    response = _request("GET", f"/guilds/{guild_id}")
    if response.status_code == 200:
        print("[discord] -> 200")
        return response.json().get("name")
    print(f"[discord] ERROR -> {response.status_code} | {_extract_discord_error(response)}")
    return None
