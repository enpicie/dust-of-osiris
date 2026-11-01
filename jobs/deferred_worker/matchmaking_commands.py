"""Worker half of the matchmaking commands: look the player up on start.gg,
work out their tier (matchmaking_rules), and grant or remove the role.

Each tier is a fixed bar to clear, so roles only move up: a request that earns a
higher tier removes lower level roles (in practice, Novice), and a request that
comes out lower than what the member holds changes nothing. Elite players also
hold Ascended (Elite is a subset of it). Fighter is the universal role anyone
can hold alongside any tier: it is added by /get-fighter-role, by a
Fighter-tier result, or as the default when a discriminator can't be verified,
and a request never removes it. /remove-matchmaking-role removes exactly the one
role the member names. Only the four matchmaking role IDs are ever added or
removed. Until all four are configured, no role is touched at all.
"""
import logging
from dataclasses import replace
from datetime import datetime, timezone

import matchmaking_rules as rules
import worker_constants as constants
import worker_discord_roles as discord_roles
import worker_messages as messages
import worker_startgg_api as startgg_api
from matchmaking_rules import Assessment, EventResult, Tier
from worker_aws_services import AWSServices
from worker_discord_roles import RoleUpdateError
from worker_startgg_api import StartggUnavailableError, StartggUser

logger = logging.getLogger()

# https://discord.com/developers/docs/resources/message#message-object-message-flags
SUPPRESS_EMBEDS = 1 << 2
EPHEMERAL = 1 << 6
SUPPRESS_NOTIFICATIONS = 1 << 12
_RESULTS_SHOWN = 5
STARTGG_PROFILE_URL = "https://www.start.gg/{slug}"


class _Refusal(Exception):
    """Stop and tell the user why (the message is shown as-is)."""


def _reply(content: str) -> dict:
    """Ephemeral, with silent mentions: roles render as mentions but nobody is
    pinged or notified (same as ResponseMessage.with_silent_pings in src).
    Link previews are suppressed so start.gg links stay one line."""
    flags = EPHEMERAL | SUPPRESS_NOTIFICATIONS | SUPPRESS_EMBEDS
    return {"content": content, "allowed_mentions": {"parse": []}, "flags": flags}


def _option(event_body: dict, name: str):
    options = event_body.get("data", {}).get("options", [])
    return next((o.get("value") for o in options if o.get("name") == name), None)


def _member(event_body: dict) -> tuple[str, str, list[str]]:
    member = event_body.get("member") or {}
    return event_body["guild_id"], member["user"]["id"], member.get("roles") or []


def _configured_role_ids() -> dict[Tier, str] | None:
    """Tier -> Discord role ID, or None unless every tier has a numeric role ID."""
    role_ids = {tier: constants.MATCHMAKING_ROLE_IDS.get(tier.name.lower(), "") for tier in Tier}
    if all(role_id.isdigit() for role_id in role_ids.values()):
        return role_ids
    return None


# ── start.gg ─────────────────────────────────────────────────────────────────

def _apply_placement_overrides(results: list[EventResult]) -> list[EventResult]:
    """Replace placements for events whose event-level standings are wrong."""
    corrected = []
    for result in results:
        phase_group_id = rules.PLACEMENT_OVERRIDE_PHASE_GROUPS.get(result.event_id)
        if phase_group_id is not None:
            placements = startgg_api.fetch_phase_group_placements(phase_group_id)
            result = replace(result, placement=placements.get(result.entrant_id))
        corrected.append(result)
    return corrected


def find_user(discriminator: str) -> StartggUser:
    """The start.gg user for a discriminator (or pasted profile link)."""
    slug = startgg_api.parse_profile_slug(discriminator)
    if slug is None:
        raise _Refusal(messages.INVALID_STARTGG_PROFILE)
    user = startgg_api.fetch_user(slug)
    if user is None:
        raise _Refusal(messages.STARTGG_PROFILE_NOT_FOUND)
    return user


def player_results(user: StartggUser) -> list[EventResult]:
    """Every MBAACC result for a start.gg user, with placement overrides applied."""
    return _apply_placement_overrides(startgg_api.fetch_mbaacc_results(user.slug, user.id))


def _verified_results(discriminator: str, discord_user_id: str) -> tuple[StartggUser, list[EventResult]]:
    """Results for a start.gg account, only if it is connected to this Discord
    user. The Discord check happens before any results are fetched."""
    user = find_user(discriminator)
    if not user.discord_ids:
        raise _Refusal(messages.STARTGG_NOT_LINKED)
    if discord_user_id not in user.discord_ids:
        logger.info(f"[matchmaking] profile {user.slug} is linked to a different Discord user than {discord_user_id}")
        raise _Refusal(messages.STARTGG_LINKED_TO_SOMEONE_ELSE)
    return user, player_results(user)


# ── Formatting ───────────────────────────────────────────────────────────────

def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _date(result: EventResult) -> str:
    if result.start_at is None:
        return "unknown date"
    return datetime.fromtimestamp(result.start_at, tz=timezone.utc).strftime("%Y-%m-%d")


def _placement(result: EventResult) -> str:
    if result.placement is not None:
        return f"{_ordinal(result.placement)} of {result.num_entrants}"
    if result.event_id in rules.PLACEMENT_OVERRIDE_PHASE_GROUPS:
        return f"outside the top 8 bracket, {result.num_entrants} entrants"
    return f"no final placement, {result.num_entrants} entrants"


def _describe(result: EventResult) -> str:
    # The tournament name carries the edition, e.g. "Midweek Melting 41".
    return f"{_placement(result)} at {result.tournament_name} ({result.wins}-{result.losses}, {_date(result)})"


def _role_mention(tier: Tier, role_ids: dict[Tier, str] | None) -> str:
    """A role mention (sent silently), or the bold label when role IDs are unset."""
    # MIRROR: src/utils/message_helper.py get_role_ping
    return f"<@&{role_ids[tier]}>" if role_ids else f"**{tier.label}**"


def _role_names(tier: Tier, role_ids: dict[Tier, str] | None) -> dict:
    """Format args {roles, noun} for the tier's role(s), e.g. "@Elite and @Ascended"."""
    tiers = rules.roles_for(tier)
    return {
        "roles": " and ".join(_role_mention(t, role_ids) for t in tiers),
        "noun": "roles" if len(tiers) > 1 else "role",
    }


def _hint(tier: Tier) -> str:
    return "\n" + messages.TIER_HINTS[tier.name.lower()]


def _no_results_line(role_ids: dict[Tier, str] | None) -> str:
    channel = f"<#{constants.NOVICE_CHANNEL_ID}>" if constants.NOVICE_CHANNEL_ID else messages.NOVICE_CHANNEL_FALLBACK
    return messages.NO_RESULTS_FOUND.format(novice=_role_mention(Tier.NOVICE, role_ids), channel=channel)


def _qualifying_results(assessment: Assessment) -> list[EventResult]:
    """The results that earned the assessed tier, each once, most recent first."""
    if assessment.tier == Tier.FIGHTER:
        hits = assessment.fighter_results
    else:
        hits = [hit for q, rule_hits in assessment.met if q.tier == assessment.tier for hit in rule_hits]
    unique = {hit.event_id: hit for hit in hits}
    return sorted(unique.values(), key=lambda r: r.start_at or 0, reverse=True)


def _grant_detail(assessment: Assessment, results: list[EventResult], role_ids: dict[Tier, str] | None) -> str:
    """Lines under "You now have ...": why, then the Fighter reminder. Ascended
    is explained by the Melt Your Blood bar rather than individual results."""
    tier = assessment.tier
    if tier == Tier.NOVICE:
        detail = (_no_results_line(role_ids) if not results else "") + _hint(tier)
    elif tier == Tier.ASCENDED:
        detail = messages.ASCENDED_BAR
    else:
        detail = messages.QUALIFYING_RESULT.format(result=_describe(_qualifying_results(assessment)[0]))
    return detail + _fighter_line(tier, role_ids)


def _already_held_detail(tier: Tier, results: list[EventResult], role_ids: dict[Tier, str] | None) -> str:
    """Lines under "You already have ...": how to move up, then the Fighter reminder."""
    no_results = _no_results_line(role_ids) if tier == Tier.NOVICE and not results else ""
    return no_results + _hint(tier) + _fighter_line(tier, role_ids)


def _fighter_line(tier: Tier, role_ids: dict[Tier, str] | None) -> str:
    if tier == Tier.FIGHTER:
        return ""
    return messages.FIGHTER_OPEN_TO_EVERYONE.format(fighter=_role_mention(Tier.FIGHTER, role_ids))


# ── Role changes ─────────────────────────────────────────────────────────────

def _change_roles(guild_id: str, user_id: str, member_roles: list[str], to_add: list[str], to_remove: list[str]) -> bool:
    """Apply role changes, adding before removing so a failure never leaves the
    member with fewer roles than before. Returns False if nothing needed to change."""
    to_add = [role_id for role_id in to_add if role_id not in member_roles]
    to_remove = [role_id for role_id in to_remove if role_id in member_roles]
    for role_id in to_add:
        discord_roles.add_member_role(guild_id, user_id, role_id)
    for role_id in to_remove:
        discord_roles.remove_member_role(guild_id, user_id, role_id)
    return bool(to_add or to_remove)


# Roles that mark a member's earned level. Fighter is universal (anyone can opt
# in), so holding it says nothing about level.
_LEVEL_TIERS = (Tier.NOVICE, Tier.ASCENDED, Tier.ELITE)


def _held_level(member_roles: list[str], role_ids: dict[Tier, str]) -> Tier | None:
    held = [tier for tier in _LEVEL_TIERS if role_ids[tier] in member_roles]
    return max(held) if held else None


def _grant_tier_roles(guild_id: str, user_id: str, member_roles: list[str], role_ids: dict[Tier, str], tier: Tier) -> bool:
    """Give the member this tier's role(s) and remove only lower level roles.
    Each tier is a fixed bar, so roles only move up: a lower tier never replaces a
    higher one (callers check that first), and Fighter is never removed here."""
    targets = rules.roles_for(tier)
    to_remove = [role_ids[t] for t in _LEVEL_TIERS if t < tier and t not in targets]
    return _change_roles(guild_id, user_id, member_roles, [role_ids[t] for t in targets], to_remove)


# ── Handlers ─────────────────────────────────────────────────────────────────

def handle_request_role(event_body: dict, aws_services: AWSServices) -> dict:
    """/request-matchmaking-role startgg_discriminator: grant the tier the player's
    results earn. If the discriminator can't be tied to this Discord account,
    add Fighter (open to everyone) and leave every other role alone."""
    try:
        guild_id, user_id, member_roles = _member(event_body)
        discriminator = _option(event_body, "startgg_discriminator") or ""
        role_ids = _configured_role_ids()

        try:
            _, results = _verified_results(discriminator, user_id)
        except _Refusal as refusal:
            logger.info(f"[matchmaking] request user={user_id} guild={guild_id} unverified; defaulting to fighter")
            detail = f"\n{refusal}{messages.LINK_DISCORD_TO_STARTGG}"
            if role_ids is None:
                return _reply(messages.ROLES_NOT_CONFIGURED.format(**_role_names(Tier.FIGHTER, None)) + detail)
            changed = _change_roles(guild_id, user_id, member_roles, [role_ids[Tier.FIGHTER]], [])
            headline = messages.ROLE_GRANTED if changed else messages.ROLE_ALREADY_HELD
            return _reply(headline.format(**_role_names(Tier.FIGHTER, role_ids)) + detail)

        assessment = rules.assess(results)
        tier = assessment.tier
        logger.info(f"[matchmaking] request user={user_id} guild={guild_id} tier={tier.name}")

        if role_ids is None:
            logger.warning("[matchmaking] role IDs not configured; no roles changed")
            return _reply(messages.ROLES_NOT_CONFIGURED.format(**_role_names(tier, None))
                          + _grant_detail(assessment, results, None))

        held = _held_level(member_roles, role_ids)
        if held is not None and held > tier:
            # Results don't get deleted, so this means start.gg is missing some.
            logger.info(f"[matchmaking] user={user_id} keeps {held.name}; results now say {tier.name}")
            return _reply(messages.ROLE_ALREADY_HELD.format(**_role_names(held, role_ids))
                          + messages.RESULTS_MAY_BE_MISSING.format(roles=_role_mention(tier, role_ids)))

        if _grant_tier_roles(guild_id, user_id, member_roles, role_ids, tier):
            return _reply(messages.ROLE_GRANTED.format(**_role_names(tier, role_ids))
                          + _grant_detail(assessment, results, role_ids))
        return _reply(messages.ROLE_ALREADY_HELD.format(**_role_names(tier, role_ids))
                      + _already_held_detail(tier, results, role_ids))
    except StartggUnavailableError:
        return _reply(messages.STARTGG_UNAVAILABLE)
    except RoleUpdateError as e:
        logger.error(f"[matchmaking] role update failed: {e}")
        return _reply(messages.ROLE_UPDATE_FAILED)


def handle_remove_role(event_body: dict, aws_services: AWSServices) -> dict:
    """/remove-matchmaking-role role: remove exactly the one named role (Novice,
    Fighter, Ascended or Elite). Naming it keeps removals intentional, e.g. an
    Elite player can drop Ascended and keep Elite."""
    try:
        guild_id, user_id, member_roles = _member(event_body)
        tier = Tier.__members__.get(str(_option(event_body, "role") or "").upper())
        if tier is None:
            return _reply(messages.UNKNOWN_ROLE)

        role_ids = _configured_role_ids()
        if role_ids is None or role_ids[tier] not in member_roles:
            return _reply(messages.ROLE_NOT_HELD.format(role=_role_mention(tier, role_ids)))

        discord_roles.remove_member_role(guild_id, user_id, role_ids[tier])
        logger.info(f"[matchmaking] removed user={user_id} guild={guild_id} tier={tier.name}")
        return _reply(messages.ROLES_REMOVED.format(roles=_role_mention(tier, role_ids), noun="role"))
    except RoleUpdateError as e:
        logger.error(f"[matchmaking] role removal failed: {e}")
        return _reply(messages.ROLE_UPDATE_FAILED)


def handle_get_fighter_role(event_body: dict, aws_services: AWSServices) -> dict:
    """/get-fighter-role: add the universal Fighter role. No other role changes."""
    try:
        guild_id, user_id, member_roles = _member(event_body)
        role_ids = _configured_role_ids()
        if role_ids is None:
            logger.warning("[matchmaking] role IDs not configured; no roles changed")
            return _reply(messages.ROLES_NOT_CONFIGURED.format(**_role_names(Tier.FIGHTER, None)))
        changed = _change_roles(guild_id, user_id, member_roles, [role_ids[Tier.FIGHTER]], [])
        logger.info(f"[matchmaking] get fighter user={user_id} guild={guild_id} changed={changed}")
        headline = messages.ROLE_GRANTED if changed else messages.ROLE_ALREADY_HELD
        return _reply(headline.format(**_role_names(Tier.FIGHTER, role_ids)))
    except RoleUpdateError as e:
        logger.error(f"[matchmaking] fighter grant failed: {e}")
        return _reply(messages.ROLE_UPDATE_FAILED)


def handle_results_view(event_body: dict, aws_services: AWSServices) -> dict:
    """/results-view startgg_discriminator: show the results behind the tier the
    player's results earn (only that tier; the full history is on start.gg)."""
    try:
        _, user_id, _ = _member(event_body)
        user, results = _verified_results(_option(event_body, "startgg_discriminator") or "", user_id)
    except _Refusal as refusal:
        return _reply(f"{refusal}{messages.LINK_DISCORD_TO_STARTGG}")
    except StartggUnavailableError:
        return _reply(messages.STARTGG_UNAVAILABLE)

    role_ids = _configured_role_ids()
    assessment = rules.assess(results)
    tier = assessment.tier
    content = messages.RESULTS_HEADER.format(player=user.gamer_tag or user.slug, slug=user.slug)
    content += messages.RESULTS_POINT_TO.format(**_role_names(tier, role_ids))
    if results:
        content += messages.RESULTS_CHECKED.format(count=len(results), events="event" if len(results) == 1 else "events")

    if tier == Tier.NOVICE:
        return _reply(content + (_no_results_line(role_ids) if not results else "") + _hint(tier))
    if tier == Tier.ASCENDED:
        return _reply(content + messages.ASCENDED_BAR)

    content += messages.RESULTS_QUALIFYING_LINK.format(url=STARTGG_PROFILE_URL.format(slug=user.slug))
    content += "".join(f"\n• {_describe(hit)}" for hit in _qualifying_results(assessment)[:_RESULTS_SHOWN])
    return _reply(content)
