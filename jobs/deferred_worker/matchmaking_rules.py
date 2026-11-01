"""Matchmaking tier rules: which role a player's start.gg results earn.

Pure data and pure functions — no I/O — so every rule is unit-testable. To
change who qualifies for what, edit QUALIFIERS (or the fighter thresholds);
nothing else needs to move.

Placements are compared as `placement <= N`. start.gg reports tied placements
as the top of the tie (5th-6th is 5, 9th-12th is 9, 33rd-48th is 33), so
"Top 6" / "Top 12" / "Top 48" line up with double-elimination tiers.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from typing import Callable


class Tier(IntEnum):
    """Matchmaking tiers, ordered weakest to strongest."""
    NOVICE = 0
    FIGHTER = 1
    ASCENDED = 2
    ELITE = 3

    @property
    def label(self) -> str:
        return self.name.capitalize()


@dataclass(frozen=True)
class EventResult:
    """One player's result in one start.gg event."""
    event_id: int
    event_name: str
    tournament_name: str
    num_entrants: int
    start_at: int | None      # unix seconds
    entrant_id: int | None
    placement: int | None     # None when there is no trustworthy final placement
    wins: int                 # set record, excluding byes
    losses: int


@dataclass(frozen=True)
class Qualifier:
    """One way to earn a tier: a placement in a set of events, optionally
    gated on bracket size and date, possibly required more than once."""
    tier: Tier
    label: str
    applies_to: Callable[[EventResult], bool]
    max_placement: int
    min_entrants: int = 0
    earliest_start: datetime | None = None
    times_required: int = 1

    def is_met_by(self, result: EventResult) -> bool:
        if not self.applies_to(result):
            return False
        if result.placement is None or result.placement > self.max_placement:
            return False
        if result.num_entrants < self.min_entrants:
            return False
        if self.earliest_start is not None:
            if result.start_at is None or result.start_at < self.earliest_start.timestamp():
                return False
        return True


@dataclass(frozen=True)
class Assessment:
    tier: Tier
    # Every qualifier met, with the results that met it (most recent first).
    met: list[tuple[Qualifier, list[EventResult]]]
    # Results that satisfy the fighter bar (most recent first).
    fighter_results: list[EventResult]


# ── Events named by link ─────────────────────────────────────────────────────
# Matched by start.gg event ID (stable even if an organizer edits the slug).
FROSTY_2024 = 1002935    # vortex-gallery-at-frosty-faustings-xvi/event/melty-blood-actress-again-current-code-pc
FROSTY_2025 = 1212830    # frosty-faustings-xvii-2025/event/melty-blood-actress-again-current-code
FROSTY_2026 = 1450995    # frosty-faustings-xviii-2026/event/melty-blood-actress-again-current-code
COMBO_BREAKER_2024 = 1049453  # all-in-together-2024-combo-breaker-community-tournaments/event/melty-blood-actress-again-current-code
COMBO_BREAKER_2025 = 1335587  # all-in-together-2025-combo-breaker-community-tournaments/event/melty-blood-actress-again-current-code
COMBO_BREAKER_2026 = 1528957  # combo-breaker-2026/event/melty-blood-actress-again-current-code
CLIMAX_OF_NIGHT_2022 = 723078   # climax-of-night-season-5-moonstrike/event/bloodstruck-mbaacc-singles
CLIMAX_OF_NIGHT_2024 = 1130786  # climax-of-night-season-6-strong-hold/event/strong-blood-mbaacc-singles
CLIMAX_OF_NIGHT_2025 = 1390782  # climax-of-night-final-season-breakadawn/event/a-bloody-finale-mbaacc-singles
ECLIPSE_2026 = 1635293   # eclipse-1st-cour/event/bloody-fights-mbaacc-singles

# Events whose event-level standings are wrong. Placements come from the named
# phase group's standings instead; an entrant outside that group has no
# placement. Frosty 2026's event standings list every top-8 player as 1st.
PLACEMENT_OVERRIDE_PHASE_GROUPS = {
    FROSTY_2026: 3151359,  # Top 8 bracket
}

# ── Series matched by name ───────────────────────────────────────────────────
TNS_NETPLAY = "TNS Melty Blood Actress Again Current Code"
MIDWEEK_MELTING = "Midweek Melting"
MELT_YOUR_BLOOD = "Melt Your Blood"

# Fighter: at least one result of 2-2 or better in a bracket this size.
FIGHTER_MIN_ENTRANTS = 24
FIGHTER_MIN_WINS = 2


def _events(*event_ids: int) -> Callable[[EventResult], bool]:
    wanted = frozenset(event_ids)
    return lambda result: result.event_id in wanted


def _series(name: str) -> Callable[[EventResult], bool]:
    """A series' main bracket: tournament or event name contains `name`
    (case-insensitive), excluding redemption brackets."""
    needle = name.casefold()

    def applies_to(result: EventResult) -> bool:
        if "redemption" in result.event_name.casefold():
            return False
        return needle in result.tournament_name.casefold() or needle in result.event_name.casefold()

    return applies_to


_JAN_1_2024 = datetime(2024, 1, 1, tzinfo=timezone.utc)

QUALIFIERS: list[Qualifier] = [
    # ── Elite ────────────────────────────────────────────────────────────────
    Qualifier(Tier.ELITE, "1st at a Midweek Melting (24+ entrants)", _series(MIDWEEK_MELTING), 1, min_entrants=24),
    Qualifier(Tier.ELITE, "Top 8 at a TNS MBAACC Netplay bracket", _series(TNS_NETPLAY), 8),
    Qualifier(Tier.ELITE, "Top 8 at Frosty Faustings 2024-2026", _events(FROSTY_2024, FROSTY_2025, FROSTY_2026), 8),
    Qualifier(Tier.ELITE, "Top 12 at Climax of Night 2024-2025", _events(CLIMAX_OF_NIGHT_2024, CLIMAX_OF_NIGHT_2025), 12),
    Qualifier(Tier.ELITE, "Top 3 at Climax of Night 2022", _events(CLIMAX_OF_NIGHT_2022), 3),
    Qualifier(Tier.ELITE, "Top 4 at Combo Breaker 2026", _events(COMBO_BREAKER_2026), 4),
    Qualifier(Tier.ELITE, "Top 8 at Eclipse 2026", _events(ECLIPSE_2026), 8),
    # ── Ascended ─────────────────────────────────────────────────────────────
    Qualifier(Tier.ASCENDED, "Top 4 at a Midweek Melting (20+ entrants, 2024 onward)", _series(MIDWEEK_MELTING), 4,
              min_entrants=20, earliest_start=_JAN_1_2024),
    Qualifier(Tier.ASCENDED, "Top 16 at a TNS MBAACC Netplay bracket", _series(TNS_NETPLAY), 16),
    Qualifier(Tier.ASCENDED, "Top 24 at Frosty Faustings 2024-2025", _events(FROSTY_2024, FROSTY_2025), 24),
    Qualifier(Tier.ASCENDED, "Top 6 at Combo Breaker 2024-2025", _events(COMBO_BREAKER_2024, COMBO_BREAKER_2025), 6),
    Qualifier(Tier.ASCENDED, "Top 32 at Climax of Night 6 (2024)", _events(CLIMAX_OF_NIGHT_2024), 32),
    Qualifier(Tier.ASCENDED, "Top 48 at Climax of Night Final/7 (2025)", _events(CLIMAX_OF_NIGHT_2025), 48),
    Qualifier(Tier.ASCENDED, "Top 32 at Combo Breaker 2026", _events(COMBO_BREAKER_2026), 32),
    Qualifier(Tier.ASCENDED, "Top 32 at Eclipse 2026", _events(ECLIPSE_2026), 32),
    Qualifier(Tier.ASCENDED, "1st at a Melt Your Blood", _series(MELT_YOUR_BLOOD), 1),
    Qualifier(Tier.ASCENDED, "Top 3 at a Melt Your Blood, twice", _series(MELT_YOUR_BLOOD), 3, times_required=2),
]

FIGHTER_LABEL = f"2-2 or better in a bracket of {FIGHTER_MIN_ENTRANTS}+"

# Discord roles a tier carries. Elite is a subset of Ascended, so Elite players
# hold both roles; every other tier holds just its own.
_TIER_ROLES = {
    Tier.ELITE: (Tier.ELITE, Tier.ASCENDED),
}


def roles_for(tier: Tier) -> tuple[Tier, ...]:
    return _TIER_ROLES.get(tier, (tier,))


def is_fighter_result(result: EventResult) -> bool:
    return result.num_entrants >= FIGHTER_MIN_ENTRANTS and result.wins >= FIGHTER_MIN_WINS


def _most_recent_first(results: list[EventResult]) -> list[EventResult]:
    return sorted(results, key=lambda r: r.start_at or 0, reverse=True)


def assess(results: list[EventResult]) -> Assessment:
    """Work out the highest tier a set of results earns, and why."""
    ordered = _most_recent_first(results)

    met = []
    for qualifier in QUALIFIERS:
        hits = [r for r in ordered if qualifier.is_met_by(r)]
        if len(hits) >= qualifier.times_required:
            met.append((qualifier, hits))

    fighter_results = [r for r in ordered if is_fighter_result(r)]

    if met:
        tier = max(qualifier.tier for qualifier, _ in met)
    elif fighter_results:
        tier = Tier.FIGHTER
    else:
        tier = Tier.NOVICE
    return Assessment(tier=tier, met=met, fighter_results=fighter_results)
