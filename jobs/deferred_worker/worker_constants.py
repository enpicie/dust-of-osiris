import json
import os

import boto3

# All injected by Terraform (terraform/infra/deferred_worker.tf). See .env.example.
AWS_REGION = os.environ.get("REGION")
DISCORD_BOT_TOKEN_SECRET_NAME = os.environ.get("DISCORD_BOT_TOKEN_SECRET_NAME")
STARTGG_API_KEY_SECRET_NAME = os.environ.get("STARTGG_API_KEY_SECRET_NAME")



def parse_role_ids(raw: str | None) -> dict[str, str]:
    """Parse the MATCHMAKING_ROLE_IDS JSON object (tier name -> Discord role ID).
    Anything unreadable yields {}, which callers treat as "not configured"."""
    try:
        parsed = json.loads(raw or "{}")
    except ValueError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(tier): str(role_id) for tier, role_id in parsed.items()}


# Discord role ID per matchmaking tier, keyed by lowercase tier name. The only
# source is terraform/infra/matchmaking_roles.tf, passed in as one JSON env var.
# A missing or non-numeric ID means "not configured" and no role is touched.
MATCHMAKING_ROLE_IDS = parse_role_ids(os.environ.get("MATCHMAKING_ROLE_IDS"))

_secret_cache: dict[str, str] = {}
_secretsmanager_client = None


def _get_secretsmanager_client():
    """Returns the shared Secrets Manager client, creating it on first use."""
    global _secretsmanager_client
    if _secretsmanager_client is None:
        _secretsmanager_client = boto3.client("secretsmanager", region_name=AWS_REGION)
    return _secretsmanager_client


def _get_secret(secret_name: str) -> str:
    """Fetches a secret's value from Secrets Manager, caching it for the warm container."""
    if secret_name not in _secret_cache:
        response = _get_secretsmanager_client().get_secret_value(SecretId=secret_name)
        _secret_cache[secret_name] = response["SecretString"]
    return _secret_cache[secret_name]


def get_discord_bot_token() -> str:
    """Fetches and caches the Discord bot token from Secrets Manager (once per cold start).

    Followups don't need it; use it for Discord REST calls made from the worker
    (roles, channel posts).
    """
    return _get_secret(DISCORD_BOT_TOKEN_SECRET_NAME)


def get_startgg_api_key() -> str:
    """Fetches and caches the start.gg API key from Secrets Manager (once per cold start)."""
    return _get_secret(STARTGG_API_KEY_SECRET_NAME)
