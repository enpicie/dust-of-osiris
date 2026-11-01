from typing import Optional

import utils.bot_messages as bot_messages
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

# Permissions Constants
MANAGE_SERVER_BIT = 0x20 # 1 << 5

# Per Discord Docs: https://discord.com/developers/docs/topics/permissions#permissions-bitwise-permission-flags
# Check permissions by doing bitwise AND with the permission integer.
# Each permission corresponds to 1 << x where x is the bit position.

def require_manage_server_permission(event: DiscordEvent) -> Optional[ResponseMessage]:
    """
    Returns a ResponseMessage refusing the action if the invoking member lacks
    the 'Manage Server' permission (bit 0x20), otherwise None.
    """
    has_permission = (event.get_user_permission_int() & MANAGE_SERVER_BIT) != 0
    if not has_permission:
        return ResponseMessage(
            content=bot_messages.REQUIRE_MANAGE_SERVER
        )
