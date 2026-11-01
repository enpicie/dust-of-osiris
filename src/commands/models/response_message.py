from typing import Dict, List, Optional
from discord import Embed

import utils.bot_messages as bot_messages
from enums import DiscordCallbackType
import commands.models.message_flags as message_flags

class ResponseMessage:
    content: str
    embeds: Optional[List[Embed]]
    allowed_mentions: Optional[Dict] = None
    flags: int = 0

    def __init__(self, content: str, embeds: List[Embed] = None):
        self.content = content
        self.embeds = embeds or []

    def with_silent_pings(self) -> "ResponseMessage":
        self.allowed_mentions = {
            "parse": [] # Disable all automatic pings
        }
        self.flags |= message_flags.SUPPRESS_NOTIFICATIONS
        return self

    def with_suppressed_embeds(self) -> "ResponseMessage":
        self.flags |= message_flags.SUPPRESS_EMBEDS
        return self

    def to_dict(self) -> dict:
        data = {
            "content": self.content,
            "embeds": [embed.to_dict() for embed in self.embeds]
        }

        if self.allowed_mentions is not None: # Set when silencing mentions
            data["allowed_mentions"] = self.allowed_mentions
        if self.flags != 0: # Default value implying no flags set
            data["flags"] = self.flags

        return {
            "type": DiscordCallbackType.MESSAGE_WITH_SOURCE,
            "data": data
        }

    @staticmethod
    def get_error_message() -> "ResponseMessage":
        return ResponseMessage(content=bot_messages.GENERAL_ERROR)
