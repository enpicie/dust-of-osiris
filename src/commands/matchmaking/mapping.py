from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
import commands.matchmaking.matchmaking_commands as matchmaking_commands

_DISCRIMINATOR_PARAM = CommandParam(
    name="startgg_discriminator",
    description="Your start.gg discriminator, e.g. a1b2c3d4 (see /matchmaking-help)",
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
        "description": "Remove your Novice, Ascended or Elite matchmaking role",
        "params": []
    },
    "get-fighter-role": {
        "function": matchmaking_commands.get_fighter_role,
        "description": "Get the Fighter role, open to everyone",
        "params": []
    },
    "remove-fighter-role": {
        "function": matchmaking_commands.remove_fighter_role,
        "description": "Remove your Fighter role",
        "params": []
    },
    "results-view": {
        "function": matchmaking_commands.results_view,
        "description": "See the start.gg results your matchmaking role is based on",
        "params": [_DISCRIMINATOR_PARAM]
    },
    "matchmaking-help": {
        "function": matchmaking_commands.matchmaking_help,
        "description": "How to find your start.gg discriminator and use the matchmaking commands",
        "params": []
    },
    "appeal-matchmaking-role": {
        "function": matchmaking_commands.appeal_matchmaking_role,
        "description": "Find out how to appeal your matchmaking role",
        "params": []
    },
}
