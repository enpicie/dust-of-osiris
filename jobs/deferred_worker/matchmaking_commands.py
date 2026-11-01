"""Worker half of the matchmaking commands: look the player up on start.gg,
work out their tier (matchmaking_rules), and grant or remove the role.

Each tier is a fixed bar to clear, so roles only move up: a request that earns a
higher tier removes lower level roles (in practice, Novice), and a request that
comes out lower than what the member holds changes nothing. Elite players also
hold Ascended (Elite is a subset of it). Fighter is the universal role anyone can hold alongside any
tier: it is added by /get-fighter-role, by a Fighter-tier result, or as the
default when a discriminator can't be verified, and only /remove-fighter-role
removes it. Only the four matchmaking role IDs are ever added or removed. Until
all four are configured, no role is touched at all.
"""
import logging
from collections import Counter
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
from worker_startgg_api import StartggUnavailableError

logger = logging.getLogger()

EPHEMERAL = 1 << 6
_DISCORD_MESSAGE_LIMIT = 2000
_HITS_SHOWN_PER_QUALIFIER = 3


class _Refusal(Exception):
    """Stop and tell the user why (the message is shown as-is)."""


def _reply(content: str) -> dict:
    # Ephemeral, and never pings: messages name roles but must not mention them.
    return {"content": content, "allowed_mentions": {"parse": []}, "flags": EPHEMERAL}


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


def _verified_results(profile: str, discord_user_id: str) -> tuple[str, list[EventResult]]:
    """Results for a start.gg profile, only if that profile is connected to this Discord user."""
    slug = startgg_api.parse_profile_slug(profile)
    if slug is None:
        raise _Refusal(messages.INVALID_STARTGG_PROFILE)

    user = startgg_api.fetch_user(slug)
    if user is None:
        raise _Refusal(messages.STARTGG_PROFILE_NOT_FOUND)
    if not user.discord_ids:
        raise _Refusal(messages.STARTGG_NOT_LINKED)
    if discord_user_id not in user.discord_ids:
        logger.info(f"[matchmaking] profile {user.slug} is linked to a different Discord user than {discord_user_id}")
        raise _Refusal(messages.STARTGG_LINKED_TO_SOMEONE_ELSE)

    results = startgg_api.fetch_mbaacc_results(user.slug, user.id)
    return user.slug, _apply_placement_overrides(results)


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


def _event_title(result: EventResult, shared_tournaments: set[str]) -> str:
    # Tournament name alone, unless the player has several events in it.
    if result.tournament_name in shared_tournaments:
        return f"{result.tournament_name} ({result.event_name})"
    return result.tournament_name


def _describe(result: EventResult, shared_tournaments: set[str] = frozenset()) -> str:
    return (
        f"{_placement(result)} at {_event_title(result, shared_tournaments)} "
        f"({result.wins}-{result.losses}, {_date(result)})"
    )


def _qualifying_line(assessment: Assessment) -> str:
    """Why the player landed on their tier, in one line."""
    if assessment.tier == Tier.NOVICE:
        return messages.NOVICE_EXPLANATION.format(fighter=rules.FIGHTER_LABEL)
    if assessment.tier == Tier.FIGHTER:
        return messages.QUALIFYING_RESULT.format(
            label=rules.FIGHTER_LABEL, result=_describe(assessment.fighter_results[0])
        )
    qualifier, hits = next((q, h) for q, h in assessment.met if q.tier == assessment.tier)
    return messages.QUALIFYING_RESULT.format(label=qualifier.label, result=_describe(hits[0]))


def _fit(lines: list[str]) -> str:
    """Join lines, dropping trailing ones (with a count) to stay under Discord's limit."""
    out = []
    for i, line in enumerate(lines):
        candidate = "\n".join(out + [line])
        footer = messages.RESULTS_TRUNCATED.format(count=len(lines) - i)
        if len(candidate) + len(footer) + 1 > _DISCORD_MESSAGE_LIMIT:
            return "\n".join(out + [footer])
        out.append(line)
    return "\n".join(out)


# ── Role changes ─────────────────────────────────────────────────────────────

def _role_names(tier: Tier) -> dict:
    """Format args for ROLE_GRANTED / ROLE_ALREADY_HELD: the tier's role names and 'role(s)'."""
    tiers = rules.roles_for(tier)
    return {
        "roles": " and ".join(f"**{t.label}**" for t in tiers),
        "noun": "roles" if len(tiers) > 1 else "role",
    }


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

        try:
            _, results = _verified_results(discriminator, user_id)
        except _Refusal as refusal:
            logger.info(f"[matchmaking] request user={user_id} guild={guild_id} unverified; defaulting to fighter")
            role_ids = _configured_role_ids()
            detail = f"\n{refusal}{messages.LINK_DISCORD_TO_STARTGG}"
            if role_ids is None:
                return _reply(messages.ROLES_NOT_CONFIGURED.format(**_role_names(Tier.FIGHTER)) + detail)
            changed = _change_roles(guild_id, user_id, member_roles, [role_ids[Tier.FIGHTER]], [])
            headline = messages.ROLE_GRANTED if changed else messages.ROLE_ALREADY_HELD
            return _reply(headline.format(**_role_names(Tier.FIGHTER)) + detail)

        assessment = rules.assess(results)
        tier = assessment.tier
        logger.info(f"[matchmaking] request user={user_id} guild={guild_id} tier={tier.name}")

        detail = _qualifying_line(assessment)
        if tier != Tier.FIGHTER:
            detail += messages.FIGHTER_OPEN_TO_EVERYONE
        if tier != Tier.ELITE:
            detail += messages.APPEAL_HINT

        role_ids = _configured_role_ids()
        if role_ids is None:
            logger.warning("[matchmaking] role IDs not configured; no roles changed")
            return _reply(messages.ROLES_NOT_CONFIGURED.format(**_role_names(tier)) + detail)

        held = _held_level(member_roles, role_ids)
        if held is not None and held > tier:
            logger.info(f"[matchmaking] user={user_id} keeps {held.name}; results now say {tier.name}")
            return _reply(messages.ROLE_ALREADY_HIGHER.format(**_role_names(held), tier=tier.label))

        changed = _grant_tier_roles(guild_id, user_id, member_roles, role_ids, tier)
        headline = messages.ROLE_GRANTED if changed else messages.ROLE_ALREADY_HELD
        return _reply(headline.format(**_role_names(tier)) + detail)
    except StartggUnavailableError:
        return _reply(messages.STARTGG_UNAVAILABLE)
    except RoleUpdateError as e:
        logger.error(f"[matchmaking] role update failed: {e}")
        return _reply(messages.ROLE_UPDATE_FAILED)


def handle_remove_role(event_body: dict, aws_services: AWSServices) -> dict:
    """/remove-matchmaking-role: remove the member's tier roles (Novice, Ascended,
    Elite). Fighter is managed separately with /remove-fighter-role."""
    try:
        guild_id, user_id, member_roles = _member(event_body)
        role_ids = _configured_role_ids()
        if role_ids is None:
            logger.warning("[matchmaking] role IDs not configured; no roles changed")
            return _reply(messages.NO_ROLE_TO_REMOVE)

        held = [tier for tier in Tier if tier != Tier.FIGHTER and role_ids[tier] in member_roles]
        keeps_fighter = role_ids[Tier.FIGHTER] in member_roles
        fighter_hint = messages.FIGHTER_KEPT if keeps_fighter else ""
        if not held:
            return _reply(messages.NO_ROLE_TO_REMOVE + fighter_hint)
        for tier in held:
            discord_roles.remove_member_role(guild_id, user_id, role_ids[tier])
        logger.info(f"[matchmaking] removed user={user_id} guild={guild_id} tiers={[t.name for t in held]}")
        removed = {"roles": " and ".join(f"**{t.label}**" for t in held), "noun": "roles" if len(held) > 1 else "role"}
        return _reply(messages.ROLES_REMOVED.format(**removed) + fighter_hint)
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
            return _reply(messages.ROLES_NOT_CONFIGURED.format(**_role_names(Tier.FIGHTER)))
        changed = _change_roles(guild_id, user_id, member_roles, [role_ids[Tier.FIGHTER]], [])
        logger.info(f"[matchmaking] get fighter user={user_id} guild={guild_id} changed={changed}")
        headline = messages.ROLE_GRANTED if changed else messages.ROLE_ALREADY_HELD
        return _reply(headline.format(**_role_names(Tier.FIGHTER)))
    except RoleUpdateError as e:
        logger.error(f"[matchmaking] fighter grant failed: {e}")
        return _reply(messages.ROLE_UPDATE_FAILED)


def handle_remove_fighter_role(event_body: dict, aws_services: AWSServices) -> dict:
    """/remove-fighter-role: remove only the Fighter role."""
    try:
        guild_id, user_id, member_roles = _member(event_body)
        role_ids = _configured_role_ids()
        if role_ids is None or role_ids[Tier.FIGHTER] not in member_roles:
            return _reply(messages.NO_FIGHTER_TO_REMOVE)
        discord_roles.remove_member_role(guild_id, user_id, role_ids[Tier.FIGHTER])
        logger.info(f"[matchmaking] removed fighter user={user_id} guild={guild_id}")
        return _reply(messages.ROLES_REMOVED.format(**_role_names(Tier.FIGHTER)))
    except RoleUpdateError as e:
        logger.error(f"[matchmaking] fighter removal failed: {e}")
        return _reply(messages.ROLE_UPDATE_FAILED)


def handle_results_view(event_body: dict, aws_services: AWSServices) -> dict:
    """/results-view startgg_discriminator: show the results the tier is worked out from."""
    try:
        _, user_id, _ = _member(event_body)
        slug, results = _verified_results(_option(event_body, "startgg_discriminator") or "", user_id)
    except _Refusal as refusal:
        return _reply(str(refusal))
    except StartggUnavailableError:
        return _reply(messages.STARTGG_UNAVAILABLE)

    assessment = rules.assess(results)
    tournament_counts = Counter(r.tournament_name for r in results)
    shared = {name for name, count in tournament_counts.items() if count > 1}

    lines = [messages.RESULTS_HEADER.format(slug=slug, tier=assessment.tier.label, count=len(results))]
    if not results:
        lines.append(messages.RESULTS_NONE)
        return _reply("\n".join(lines))

    shown: set[int] = set()
    sections = [(q.tier, q.label, hits) for q, hits in sorted(assessment.met, key=lambda m: -m[0].tier)]
    if assessment.fighter_results:
        sections.append((Tier.FIGHTER, rules.FIGHTER_LABEL, assessment.fighter_results))
    if sections:
        lines.append(messages.RESULTS_QUALIFYING_HEADER)
        for tier, label, hits in sections:
            lines.append(f"**{tier.label}**: {label}")
            for hit in hits[:_HITS_SHOWN_PER_QUALIFIER]:
                lines.append(f"• {_describe(hit, shared)}")
                shown.add(hit.event_id)

    others = sorted((r for r in results if r.event_id not in shown), key=lambda r: r.start_at or 0, reverse=True)
    if others:
        lines.append(messages.RESULTS_OTHER_HEADER)
        lines.extend(f"• {_describe(r, shared)}" for r in others)

    # Long histories overflow into the trailing "other results" lines, which get cut first.
    return _reply(_fit(lines))
