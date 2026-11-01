from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, List, Callable
from discord import AppCommandOptionType

if TYPE_CHECKING:
    from aws_services import AWSServices
    from commands.models.discord_event import DiscordEvent
    from commands.models.autocomplete_response import AutocompleteResponse

@dataclass
class ParamChoice:
    name: str
    value: Any

@dataclass
class CommandParam:
  name: str
  description: str # Max allowed length by Discord is 100 chars.
  param_type: AppCommandOptionType
  required: bool
  choices: Optional[List[ParamChoice]]
  autocomplete: bool = False
  autocomplete_handler: Optional[Callable[["DiscordEvent", "AWSServices"], "AutocompleteResponse"]] = None

  def to_dict(self) -> dict:
      param_dict = {
          "name": self.name,
          "description": self.description or "No description",
          "type": self.param_type.value,
          "required": self.required,
          "autocomplete": self.autocomplete
      }
      if self.choices:
          param_dict["choices"] = [{"name": choice.name, "value": choice.value} for choice in self.choices]
      return param_dict
