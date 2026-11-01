import json
import os

#######################################
# Environment Variables              #
#######################################
# All injected by Terraform (terraform/infra/main.tf). See .env.example.
AWS_REGION = os.environ.get("REGION")
BOT_PUBLIC_KEY = os.environ.get("PUBLIC_KEY")
DISCORD_BOT_TOKEN_SECRET_NAME = os.environ.get("DISCORD_BOT_TOKEN_SECRET_NAME")
SQS_DEFERRED_WORKER_QUEUE_URL = os.environ.get("DEFERRED_WORKER_QUEUE_URL")


def _parse_role_ids(raw: str | None) -> dict[str, str]:
    # MIRROR: jobs/deferred_worker/worker_constants.py parse_role_ids
    try:
        parsed = json.loads(raw or "{}")
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}


# Tier name -> Discord role ID, from terraform/infra/matchmaking_roles.tf (used to
# mention roles in replies; role changes happen in the deferred worker).
MATCHMAKING_ROLE_IDS = _parse_role_ids(os.environ.get("MATCHMAKING_ROLE_IDS"))

########################################
# Discord Data Constants              #
########################################
# Discord expects to see this response to its "ping pong" verification request
PING_PONG_RESPONSE = { "type": 1 }
