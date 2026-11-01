from commands.models.command_mapping import CommandMapping
import commands.general.general_commands as general_commands

general_commands_mapping: CommandMapping = {
    "ping": {
        "function": general_commands.ping,
        "description": "Check that the bot is alive",
        "params": []
    },
}
