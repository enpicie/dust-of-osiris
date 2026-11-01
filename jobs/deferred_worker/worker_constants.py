import os

import boto3

# All injected by Terraform (terraform/infra/deferred_worker.tf). See .env.example.
AWS_REGION = os.environ.get("REGION")
DISCORD_BOT_TOKEN_SECRET_NAME = os.environ.get("DISCORD_BOT_TOKEN_SECRET_NAME")
STARTGG_API_KEY_SECRET_NAME = os.environ.get("STARTGG_API_KEY_SECRET_NAME")

# Discord role ID per matchmaking tier, keyed by tier name. Set in
# terraform/infra/matchmaking_roles.tf; anything that isn't a numeric Discord
# ID (e.g. the placeholder) means "not configured" and no role is touched.
MATCHMAKING_ROLE_IDS = {
    tier: os.environ.get(f"MATCHMAKING_ROLE_ID_{tier.upper()}", "")
    for tier in ("novice", "fighter", "ascended", "elite")
}

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
