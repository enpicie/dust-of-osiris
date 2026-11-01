import commands.matchmaking.startgg_profile as startgg_profile
import constants
import utils.message_helper as message_helper
import utils.bot_messages as bot_messages
import utils.deferred_dispatch as deferred_dispatch
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

# Role lookups call start.gg and the Discord API, which can exceed Discord's 3s
# deadline, so these validate inline and hand off to jobs/deferred_worker
# (matchmaking_commands.py). Every reply is ephemeral.

# Choice value -> label for /remove-matchmaking-role. Values are the worker's
# tier names (jobs/deferred_worker/matchmaking_rules.py Tier, lowercased).
ROLE_CHOICES = {
    "novice": "Novice",
    "fighter": "Fighter",
    "ascended": "Ascended",
    "elite": "Elite",
}


def _reply(content: str) -> ResponseMessage:
    return ResponseMessage(content=content).with_ephemeral()


def _in_server(event: DiscordEvent) -> bool:
    return "guild_id" in event.event_body and "member" in event.event_body


def _dispatch_with_discriminator(command_name: str, event: DiscordEvent, aws_services: AWSServices,
                                 placeholder: str) -> ResponseMessage:
    """Validate the start.gg discriminator inline, then hand off to the worker."""
    if not _in_server(event):
        return _reply(bot_messages.SERVER_ONLY)
    discriminator = event.get_command_input_value("startgg_discriminator")
    if startgg_profile.parse_profile_slug(discriminator) is None:
        return _reply(bot_messages.INVALID_STARTGG_PROFILE)

    deferred_dispatch.dispatch(command_name, event, aws_services)
    return _reply(placeholder)


def _dispatch_role_change(command_name: str, event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    if not _in_server(event):
        return _reply(bot_messages.SERVER_ONLY)

    deferred_dispatch.dispatch(command_name, event, aws_services)
    return _reply(bot_messages.UPDATING_ROLES)


def request_matchmaking_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Grant the matchmaking role the caller's start.gg results earn."""
    return _dispatch_with_discriminator("request-matchmaking-role", event, aws_services, bot_messages.CHECKING_AND_ASSIGNING)


def remove_matchmaking_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Remove the one matchmaking role the caller names."""
    if _in_server(event) and event.get_command_input_value("role") not in ROLE_CHOICES:
        return _reply(bot_messages.UNKNOWN_ROLE)
    return _dispatch_role_change("remove-matchmaking-role", event, aws_services)


def get_fighter_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Give the caller the universal Fighter role."""
    return _dispatch_role_change("get-fighter-role", event, aws_services)


def results_view(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Show the start.gg results the caller's matchmaking role is worked out from."""
    return _dispatch_with_discriminator("results-view", event, aws_services, bot_messages.CHECKING_STARTGG)


def _role_mention(tier: str) -> str:
    """A role mention by tier name (sent silently), or the bold label if role IDs are unset."""
    role_id = constants.MATCHMAKING_ROLE_IDS.get(tier, "")
    return message_helper.get_role_ping(role_id) if role_id.isdigit() else f"**{ROLE_CHOICES[tier]}**"


def help_overview(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """How matchmaking roles work. Mentions the roles silently."""
    content = bot_messages.HELP.format(
        novice=_role_mention("novice"), ascended=_role_mention("ascended"), elite=_role_mention("elite")
    )
    return _reply(content).with_silent_pings().with_suppressed_embeds()


def help_commands(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """List the matchmaking commands. Mentions @Fighter silently."""
    return _reply(bot_messages.HELP_COMMANDS.format(fighter=_role_mention("fighter"))).with_silent_pings()


def help_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Explain how to find a start.gg discriminator and connect Discord on start.gg."""
    return _reply(bot_messages.HELP_STARTGG).with_suppressed_embeds()


def appeal_matchmaking_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Tell the caller how to appeal their matchmaking role."""
    return _reply(bot_messages.APPEAL)
