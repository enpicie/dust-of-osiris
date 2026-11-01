import json
import traceback

import bot
import constants
import utils.discord_auth_helper as auth_helper
import aws_client
from commands.models.response_message import ResponseMessage
from enums import DiscordInteractionType


def lambda_handler(event, context):
    """Entry point for Discord interaction requests. Verifies the request
    signature, dispatches commands/autocomplete to the bot, and returns the
    Discord interaction response dict."""
    route = event.get("routeKey") or event.get("rawPath") or event.get("path")
    print(f"[lambda_handler] Received event: route={route} body_length={len(event.get('body') or '')}")

    try:
        auth_helper.verify_signature(event)
    except auth_helper.SignatureVerificationError as e:
        raise Exception(f"[UNAUTHORIZED] Invalid request signature: {e}") from e
    except Exception as e:
        raise Exception(f"[UNAUTHORIZED] Invalid request signature: {e}") from e

    if not event["body"]:
        return {"message": "Request is not Lambda event: 'body-json' not found"}

    body = json.loads(event["body"])

    if auth_helper.is_ping_pong(body):
        print("[lambda_handler] discord_auth_helper.is_ping_pong: True")
        response = constants.PING_PONG_RESPONSE
    else:
        try:
            interaction_type = body.get("type")
            interaction_id = body.get("id")
            print(f"[lambda_handler] Interaction type: {interaction_type} interaction_id={interaction_id}")
            if interaction_type == DiscordInteractionType.APPLICATION_COMMAND:
                response = bot.process_bot_command(body, aws_client.get_aws_services())
            elif interaction_type == DiscordInteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
                response = bot.process_input_autocomplete(body, aws_client.get_aws_services())
            else:
                raise ValueError(f"Unsupported interaction type: {interaction_type}")
        except Exception as e:
            print(f"[lambda_handler] unhandled error: {type(e).__name__}: {e}")
            print(f"[lambda_handler] {traceback.format_exc()}")
            response = ResponseMessage.get_error_message().to_dict()

    response_data = response.get("data") or {}
    print(f"[lambda_handler] Response: type={response.get('type')} content_length={len(str(response_data.get('content') or ''))}")
    return response
