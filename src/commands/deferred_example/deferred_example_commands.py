import utils.deferred_dispatch as deferred_dispatch
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def slow_echo(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Example of a deferred command: validate inline, hand the work to the
    deferred worker, and answer with a placeholder before Discord's 3s deadline.

    The worker (jobs/deferred_worker/slow_echo_commands.py) does the work and
    posts the real answer as a followup to this interaction.
    """
    text = event.get_command_input_value("text")
    if not text or not text.strip():
        # Validation errors are cheap — answer them inline, don't enqueue.
        raise ValueError("Give me some text to echo.")

    deferred_dispatch.dispatch("slow-echo", event, aws_services)
    return ResponseMessage(content="⏳ Working on it...")
