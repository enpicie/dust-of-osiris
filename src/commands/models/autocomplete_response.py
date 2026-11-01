from typing import List

from enums import DiscordCallbackType
from commands.models.command_param import ParamChoice


class AutocompleteResponse:
    choices: List[ParamChoice]

    def __init__(self, choices: List[ParamChoice]):
        self.choices = choices

    def to_dict(self) -> dict:
        return {
            "type": DiscordCallbackType.APPLICATION_COMMAND_AUTOCOMPLETE_RESULT,
            "data": {
                "choices": [{"name": c.name, "value": c.value} for c in self.choices]
            }
        }
