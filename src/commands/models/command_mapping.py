from typing import Callable, List, TypedDict

from aws_services import AWSServices
from commands.models.command_param import CommandParam
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

class CommandEntry(TypedDict):
    function: Callable[[DiscordEvent, AWSServices], ResponseMessage]
    description: str
    params: List[CommandParam]

CommandMapping = dict[str, CommandEntry]
