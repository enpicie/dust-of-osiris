"""Hand a slash command's work to the deferred worker Lambda.

Discord discards an interaction response that arrives later than 3 seconds. Any
command whose work can exceed that budget answers immediately with a placeholder
and enqueues the real work here; the worker posts the result as a followup.
"""
import json
import time

from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent


def dispatch(command_name: str, event: DiscordEvent, aws_services: AWSServices) -> None:
    """Enqueue a command's interaction payload for the deferred worker.

    :param command_name: Slash command name the worker dispatches on.
    :param event: The Discord interaction being deferred — its token is what the
                  worker posts the followup to, so the whole body is passed along.
    :param aws_services: Shared AWS service clients.
    """
    payload = json.dumps({
        "command_name": command_name,
        "event_body": event.event_body,
        "enqueued_at": time.time(),
    })
    aws_services.deferred_worker_sqs_queue.send_message(MessageBody=payload)
    print(f"[deferred] dispatched {command_name!r} to the deferred worker")
