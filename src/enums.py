from enum import IntEnum

class DiscordInteractionType(IntEnum):
    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5

class DiscordCallbackType(IntEnum):
    PONG = 1
    MESSAGE_WITH_SOURCE = 4         # CHANNEL_MESSAGE_WITH_SOURCE but omitting CHANNEL for brevity in refs
    DEFERRED_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6     # only for component interactions
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8
    MODAL = 9
