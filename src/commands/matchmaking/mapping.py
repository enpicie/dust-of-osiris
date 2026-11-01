from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
import commands.matchmaking.matchmaking_commands as matchmaking_commands

_DISCRIMINATOR_PARAM = CommandParam(
    name="startgg_discriminator",
    description="Your start.gg discriminator, e.g. a1b2c3d4 (see /help-startgg)",
    param_type=AppCommandOptionType.string,
    required=True,
    choices=None,
)

matchmaking_commands_mapping: CommandMapping = {
    "request-matchmaking-role": {
        "function": matchmaking_commands.request_matchmaking_role,
        "description": "Get the matchmaking role your start.gg results qualify you for",
        "params": [_DISCRIMINATOR_PARAM]
    },
    "remove-matchmaking-role": {
        "function": matchmaking_commands.remove_matchmaking_role,
        "description": "Remove one of your matchmaking roles",
        "params": [
            CommandParam(
                name="role",
                description="The matchmaking role to remove",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[ParamChoice(name=label, value=value) for value, label in matchmaking_commands.ROLE_CHOICES.items()],
            ),
        ]
    },
    "get-fighter-role": {
        "function": matchmaking_commands.get_fighter_role,
        "description": "Get the Fighter role, open to everyone",
        "params": []
    },
    "results-view": {
        "function": matchmaking_commands.results_view,
        "description": "See the start.gg results your matchmaking role is based on",
        "params": [_DISCRIMINATOR_PARAM]
    },
    "help": {
        "function": matchmaking_commands.help_overview,
        "description": "How the matchmaking roles work",
        "params": []
    },
    "help-commands": {
        "function": matchmaking_commands.help_commands,
        "description": "List the matchmaking commands",
        "params": []
    },
    "help-startgg": {
        "function": matchmaking_commands.help_startgg,
        "description": "How to find your start.gg discriminator and connect Discord on start.gg",
        "params": []
    },
    "appeal-matchmaking-role": {
        "function": matchmaking_commands.appeal_matchmaking_role,
        "description": "Find out how to appeal your matchmaking role",
        "params": []
    },
}
