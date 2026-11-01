import commands.matchmaking.startgg_profile as startgg_profile
import utils.bot_messages as bot_messages
import utils.deferred_dispatch as deferred_dispatch
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

# Role lookups call start.gg and the Discord API, which can exceed Discord's 3s
# deadline, so these validate inline and hand off to jobs/deferred_worker
# (matchmaking_commands.py). Every reply is ephemeral.


def _reply(content: str) -> ResponseMessage:
    return ResponseMessage(content=content).with_ephemeral()


def _in_server(event: DiscordEvent) -> bool:
    return "guild_id" in event.event_body and "member" in event.event_body


def _dispatch_with_discriminator(command_name: str, event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Validate the start.gg discriminator inline, then hand off to the worker."""
    if not _in_server(event):
        return _reply(bot_messages.SERVER_ONLY)
    discriminator = event.get_command_input_value("startgg_discriminator")
    if startgg_profile.parse_profile_slug(discriminator) is None:
        return _reply(bot_messages.INVALID_STARTGG_PROFILE)

    deferred_dispatch.dispatch(command_name, event, aws_services)
    return _reply(bot_messages.CHECKING_STARTGG)


def _dispatch_role_change(command_name: str, event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    if not _in_server(event):
        return _reply(bot_messages.SERVER_ONLY)

    deferred_dispatch.dispatch(command_name, event, aws_services)
    return _reply(bot_messages.UPDATING_ROLES)


def request_matchmaking_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Grant the matchmaking role the caller's start.gg results earn."""
    return _dispatch_with_discriminator("request-matchmaking-role", event, aws_services)


def remove_matchmaking_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Remove the caller's tier role(s): Novice, Ascended, Elite."""
    return _dispatch_role_change("remove-matchmaking-role", event, aws_services)


def get_fighter_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Give the caller the universal Fighter role."""
    return _dispatch_role_change("get-fighter-role", event, aws_services)


def remove_fighter_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Remove the caller's Fighter role."""
    return _dispatch_role_change("remove-fighter-role", event, aws_services)


def results_view(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Show the start.gg results the caller's matchmaking role is worked out from."""
    return _dispatch_with_discriminator("results-view", event, aws_services)


def matchmaking_help(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Explain how to find a start.gg discriminator and use the matchmaking commands."""
    return _reply(bot_messages.MATCHMAKING_HELP)


def appeal_matchmaking_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Tell the caller how to appeal their matchmaking role."""
    return _reply(bot_messages.APPEAL)
