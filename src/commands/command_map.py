from commands.models.command_mapping import CommandMapping

# Command self-discovery: each group under commands/<group>/ exposes its
# CommandMapping in mapping.py; merge it in here. bot.py dispatches from this
# dict and scripts/register_commands.py registers every entry with Discord.
# One group per line, trailing commas, so adding or deleting a group is one line.
from commands.general.mapping import general_commands_mapping
from commands.deferred_example.mapping import deferred_example_commands_mapping

command_map: CommandMapping = {
    **general_commands_mapping,
    **deferred_example_commands_mapping,
}
