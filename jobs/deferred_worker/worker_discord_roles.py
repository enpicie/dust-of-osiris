"""Add and remove a member's roles through the Discord REST API (bot token).

Requires the bot to have Manage Roles, with its own role ranked above every
role it grants. Callers pass only matchmaking role IDs; nothing here reads or
changes any other role.
"""
import logging

import requests

import worker_constants as constants

logger = logging.getLogger()

# MIRROR: src/utils/discord_api_helper.py DISCORD_API_BASE_URL — keep in sync.
DISCORD_API_BASE = "https://discord.com/api/v10"

_AUDIT_LOG_REASON = "Matchmaking role update requested by the member"


class RoleUpdateError(Exception):
    """Discord refused or failed a role change (usually missing permission or hierarchy)."""


def _member_role_request(method: str, guild_id: str, user_id: str, role_id: str) -> None:
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    headers = {
        "Authorization": f"Bot {constants.get_discord_bot_token()}",
        "X-Audit-Log-Reason": _AUDIT_LOG_REASON,
    }
    try:
        response = requests.request(method, url, headers=headers, timeout=10)
    except requests.RequestException as e:
        logger.error(f"[discord] {method} member role failed guild={guild_id} user={user_id} role={role_id}: {type(e).__name__}")
        raise RoleUpdateError() from e

    logger.info(f"[discord] {method} member role guild={guild_id} user={user_id} role={role_id} status={response.status_code}")
    if response.status_code != 204:
        raise RoleUpdateError(f"HTTP {response.status_code}")


def add_member_role(guild_id: str, user_id: str, role_id: str) -> None:
    _member_role_request("PUT", guild_id, user_id, role_id)


def remove_member_role(guild_id: str, user_id: str, role_id: str) -> None:
    _member_role_request("DELETE", guild_id, user_id, role_id)
