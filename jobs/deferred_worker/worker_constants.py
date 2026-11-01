import os

import boto3

# All injected by Terraform (terraform/infra/deferred_worker.tf). See .env.example.
AWS_REGION = os.environ.get("REGION")
DISCORD_BOT_TOKEN_SECRET_NAME = os.environ.get("DISCORD_BOT_TOKEN_SECRET_NAME")

_discord_bot_token = None
_secretsmanager_client = None


def _get_secretsmanager_client():
    """Returns the shared Secrets Manager client, creating it on first use."""
    global _secretsmanager_client
    if _secretsmanager_client is None:
        _secretsmanager_client = boto3.client("secretsmanager", region_name=AWS_REGION)
    return _secretsmanager_client


def get_discord_bot_token() -> str:
    """Fetches and caches the Discord bot token from Secrets Manager (once per cold start).

    Followups don't need it; use it for Discord REST calls made from the worker
    (roles, channel posts).
    """
    global _discord_bot_token
    if _discord_bot_token is None:
        response = _get_secretsmanager_client().get_secret_value(SecretId=DISCORD_BOT_TOKEN_SECRET_NAME)
        _discord_bot_token = response["SecretString"]
    return _discord_bot_token
