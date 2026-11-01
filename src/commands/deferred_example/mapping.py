from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
import commands.deferred_example.deferred_example_commands as deferred_example_commands

# Example group showing the deferred-worker pattern. Replace it with your own
# (and its line in command_map.py).
deferred_example_commands_mapping: CommandMapping = {
    "slow-echo": {
        "function": deferred_example_commands.slow_echo,
        "description": "Echo text back via the deferred worker (example of work over 3s)",
        "params": [
            CommandParam(
                name="text",
                description="Text to echo back",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
            ),
        ]
    },
}
