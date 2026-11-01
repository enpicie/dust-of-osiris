from dataclasses import dataclass
from typing import List
from discord import AppCommandOptionType

@dataclass
class DiscordInputParam:
    name: str
    type: AppCommandOptionType
    value: str

class DiscordEvent:
    event_body: dict

    def __init__(self, event_body: dict):
        self.event_body = event_body

    def _get_event_field(self, *keys: str) -> any:
        """Access a nested field in `self.event_body` by path and return the value.

        Raises KeyError("Missing required field: a.b.c") if any segment is missing or not a dict.
        """
        cur = self.event_body
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                raise KeyError(f"Missing required field: {'.'.join(keys)}")
            cur = cur[k]
        return cur

    def get_command_name(self) -> str:
        return self._get_event_field("data", "name")

    def get_all_command_inputs(self) -> List[DiscordInputParam]:
        inputs = []
        options = self._get_event_field("data", "options") if "options" in self._get_event_field("data") else []
        for option in options:
            inputs.append(DiscordInputParam(
                name=option["name"],
                type=AppCommandOptionType(option["type"]),
                value=option["value"]
            ))
        return inputs

    def get_command_input_value(self, input_name: str) -> any:
        inputs = self.get_all_command_inputs()
        input = next((input for input in inputs if input.name == input_name), None)
        return input.value if input else None

    def get_server_id(self) -> str:
        return self._get_event_field("guild_id")

    def get_channel_id(self) -> str:
        return self._get_event_field("channel_id")

    def get_user_id(self) -> str:
        return self._get_event_field("member", "user", "id")

    def get_username(self) -> str:
        return self._get_event_field("member", "user", "username")

    def get_user_permission_int(self) -> int:
        return int(self._get_event_field("member", "permissions"))

    def get_user_roles(self) -> List[str]:
        return self._get_event_field("member", "roles")

    def get_user_nick(self) -> str | None:
        member = self.event_body.get("member", {})
        return member.get("nick")

    def get_user_global_name(self) -> str | None:
        user = self.event_body.get("member", {}).get("user", {})
        return user.get("global_name")

    def get_display_name(self) -> str:
        return self.get_user_nick() or self.get_user_global_name() or self.get_username()
