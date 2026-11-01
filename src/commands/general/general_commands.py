from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def ping(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Smallest possible command: proves the endpoint, signature check and dispatch all work."""
    return ResponseMessage(content="Pong!")
