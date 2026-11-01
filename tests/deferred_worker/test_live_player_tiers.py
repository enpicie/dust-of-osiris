"""Live start.gg check: known players land on their expected matchmaking roles.

Runs the same lookup the bot does (find_user -> player_results -> assess) against
the real start.gg API, minus the Discord-account check, which needs each
player's own Discord ID. It only runs when STARTGG_API_KEY is set (CI's "Live
player tiers" step); without it every test here skips, so `make test` stays
offline.

Expectations drift as these players post new results. That's expected: when
one fails, check the report, then update PLAYERS.

Before asserting anything, it prints a report (player tag, discriminator,
roles, the reason) and, in GitHub Actions, adds it to the job summary.
"""
import os
import unittest
from dataclasses import dataclass
from unittest.mock import patch

import matchmaking_commands
import matchmaking_rules as rules
import worker_constants as constants
from matchmaking_rules import Assessment, Tier

# start.gg discriminator -> expected tier.
PLAYERS = {
    "5f6cb09c": Tier.NOVICE,
    "8b6671e6": Tier.NOVICE,
    "65d25963": Tier.FIGHTER,
    "50be98bb": Tier.FIGHTER,
    "47b3df8d": Tier.ASCENDED,
    "c8f45227": Tier.ASCENDED,
    "ec190c0a": Tier.ELITE,
    "eb898304": Tier.ELITE,
}


@dataclass
class _Row:
    discriminator: str
    expected: Tier
    player: str = "?"
    tier: Tier | None = None
    reason: str = ""
    events: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.tier == self.expected


def _roles(tier: Tier | None) -> str:
    return ", ".join(t.label for t in rules.roles_for(tier)) if tier is not None else "-"


def _reason(assessment: Assessment) -> str:
    if assessment.tier in (Tier.ELITE, Tier.ASCENDED):
        label, hits = next((q.label, hits) for q, hits in assessment.met if q.tier == assessment.tier)
        return f"{label}: {hits[0].tournament_name}"
    if assessment.tier == Tier.FIGHTER:
        return f"{rules.FIGHTER_LABEL}: {assessment.fighter_results[0].tournament_name}"
    return f"no result of {rules.FIGHTER_LABEL}"


def _lookup(discriminator: str, expected: Tier) -> _Row:
    row = _Row(discriminator, expected)
    try:
        user = matchmaking_commands.find_user(discriminator)
        row.player = user.gamer_tag or user.slug
        results = matchmaking_commands.player_results(user)
        assessment = rules.assess(results)
        row.tier, row.reason, row.events = assessment.tier, _reason(assessment), len(results)
    except Exception as e:  # report every player, even when one lookup fails
        row.error = f"{type(e).__name__}: {e}"
    return row


def _report(rows: list[_Row]) -> None:
    header = ("Discriminator", "Player", "Roles", "Expected roles", "Events", "Reason", "Result")
    table = [
        (r.discriminator, r.player, _roles(r.tier), _roles(r.expected), str(r.events),
         r.error or r.reason, "OK" if r.ok else "MISMATCH")
        for r in rows
    ]
    widths = [max(len(h), *(len(t[i]) for t in table)) for i, h in enumerate(header)]
    line = lambda cells: "  ".join(c.ljust(w) for c, w in zip(cells, widths))  # noqa: E731
    print("\n\n=== Live player tier report (start.gg) ===")
    print(line(header))
    print(line(["-" * w for w in widths]))
    for cells in table:
        print(line(cells))
    print()

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("### Live player tier report (start.gg)\n\n")
            summary.write("| " + " | ".join(header) + " |\n|" + "---|" * len(header) + "\n")
            for cells in table:
                summary.write("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |\n")
            summary.write("\n")


class TestLivePlayerTiers(unittest.TestCase):
    rows: list[_Row] = []

    @classmethod
    def setUpClass(cls):
        api_key = os.environ.get("STARTGG_API_KEY")
        if not api_key:
            raise unittest.SkipTest("STARTGG_API_KEY not set; live start.gg checks skipped")
        with patch.object(constants, "get_startgg_api_key", return_value=api_key):
            cls.rows = [_lookup(d, expected) for d, expected in PLAYERS.items()]
        _report(cls.rows)

    def test_each_player_gets_their_expected_roles(self):
        for row in self.rows:
            with self.subTest(discriminator=row.discriminator, player=row.player):
                self.assertIsNone(row.error)
                self.assertEqual(
                    row.tier, row.expected,
                    f"{row.player} ({row.discriminator}) got {_roles(row.tier)}, expected {_roles(row.expected)}",
                )

    def test_elite_players_also_get_ascended(self):
        for row in self.rows:
            if row.tier == Tier.ELITE:
                with self.subTest(discriminator=row.discriminator):
                    self.assertEqual(rules.roles_for(row.tier), (Tier.ELITE, Tier.ASCENDED))


if __name__ == "__main__":
    unittest.main()
