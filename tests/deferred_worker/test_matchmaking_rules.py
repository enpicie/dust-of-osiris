import unittest
from dataclasses import replace
from datetime import datetime, timezone

import matchmaking_rules as rules
from matchmaking_rules import EventResult, Tier

_2023 = int(datetime(2023, 6, 1, tzinfo=timezone.utc).timestamp())
_2025 = int(datetime(2025, 6, 1, tzinfo=timezone.utc).timestamp())


def _result(event_id: int = 1, *, placement: int | None = 50, num_entrants: int = 100, wins: int = 0, losses: int = 2,
            tournament_name: str = "Some Local", event_name: str = "MBAACC Singles", start_at: int = _2025) -> EventResult:
    return EventResult(
        event_id=event_id, event_name=event_name, tournament_name=tournament_name, num_entrants=num_entrants,
        start_at=start_at, entrant_id=1000 + event_id, placement=placement, wins=wins, losses=losses,
    )


def _tns(placement: int, event_name: str = "Melty Blood Actress Again Current Code") -> EventResult:
    return _result(500, placement=placement, num_entrants=173, event_name=event_name,
                   tournament_name="TNS Melty Blood Actress Again Current Code #4 (PC)")


def _midweek(event_id: int, placement: int, num_entrants: int, start_at: int = _2025) -> EventResult:
    return _result(event_id, placement=placement, num_entrants=num_entrants, start_at=start_at,
                   tournament_name=f"Midweek Melting {event_id}", event_name="Midweek Melting Bracket")


def _melt_your_blood(event_id: int, placement: int) -> EventResult:
    return _result(event_id, placement=placement, num_entrants=24,
                   tournament_name=f"Melt Your Blood {event_id}", event_name="Melt Your Blood Pools + Top 8")


def _tier(*results: EventResult) -> Tier:
    return rules.assess(list(results)).tier


class TestBaseTiers(unittest.TestCase):
    def test_no_results_is_novice(self):
        self.assertEqual(_tier(), Tier.NOVICE)

    def test_results_below_two_wins_are_novice(self):
        self.assertEqual(_tier(_result(wins=1, losses=2), _result(2, wins=0, losses=2)), Tier.NOVICE)

    def test_two_wins_in_a_24_person_bracket_is_fighter(self):
        self.assertEqual(_tier(_result(num_entrants=24, wins=2, losses=2)), Tier.FIGHTER)

    def test_two_wins_in_a_bracket_under_24_is_not_fighter(self):
        self.assertEqual(_tier(_result(num_entrants=23, wins=5, losses=0)), Tier.NOVICE)


class TestNamedEvents(unittest.TestCase):
    def test_frosty_top_8_is_elite_and_top_24_is_ascended(self):
        for event_id in (rules.FROSTY_2024, rules.FROSTY_2025):
            with self.subTest(event_id=event_id):
                self.assertEqual(_tier(_result(event_id, placement=7)), Tier.ELITE)
                self.assertEqual(_tier(_result(event_id, placement=17)), Tier.ASCENDED)
                self.assertEqual(_tier(_result(event_id, placement=25, wins=0)), Tier.NOVICE)

    def test_frosty_2026_counts_for_elite_only(self):
        self.assertEqual(_tier(_result(rules.FROSTY_2026, placement=5)), Tier.ELITE)
        self.assertEqual(_tier(_result(rules.FROSTY_2026, placement=None, wins=0)), Tier.NOVICE)

    def test_frosty_2026_placement_comes_from_its_top_8_bracket(self):
        self.assertIn(rules.FROSTY_2026, rules.PLACEMENT_OVERRIDE_PHASE_GROUPS)

    def test_combo_breaker(self):
        for event_id in (rules.COMBO_BREAKER_2024, rules.COMBO_BREAKER_2025):
            with self.subTest(event_id=event_id):
                self.assertEqual(_tier(_result(event_id, placement=5)), Tier.ASCENDED)
                self.assertEqual(_tier(_result(event_id, placement=7, wins=0)), Tier.NOVICE)
        self.assertEqual(_tier(_result(rules.COMBO_BREAKER_2026, placement=4)), Tier.ELITE)
        self.assertEqual(_tier(_result(rules.COMBO_BREAKER_2026, placement=5)), Tier.ASCENDED)
        self.assertEqual(_tier(_result(rules.COMBO_BREAKER_2026, placement=25)), Tier.ASCENDED)
        self.assertEqual(_tier(_result(rules.COMBO_BREAKER_2026, placement=33, wins=0)), Tier.NOVICE)

    def test_climax_of_night(self):
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2022, placement=3)), Tier.ELITE)
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2022, placement=4, wins=0)), Tier.NOVICE)
        # 2024-2025: Top 16 is Elite (13th-16th is reported as 13); 17th is not.
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2024, placement=13)), Tier.ELITE)
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2024, placement=17)), Tier.ASCENDED)
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2024, placement=25)), Tier.ASCENDED)
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2024, placement=33, wins=0)), Tier.NOVICE)
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2025, placement=13)), Tier.ELITE)
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2025, placement=17)), Tier.ASCENDED)
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2025, placement=33)), Tier.ASCENDED)
        self.assertEqual(_tier(_result(rules.CLIMAX_OF_NIGHT_2025, placement=49, wins=0)), Tier.NOVICE)

    def test_eclipse_2026(self):
        self.assertEqual(_tier(_result(rules.ECLIPSE_2026, placement=7)), Tier.ELITE)
        self.assertEqual(_tier(_result(rules.ECLIPSE_2026, placement=25)), Tier.ASCENDED)
        self.assertEqual(_tier(_result(rules.ECLIPSE_2026, placement=33, wins=0)), Tier.NOVICE)


class TestSeries(unittest.TestCase):
    def test_tns_top_8_is_elite_and_top_16_is_ascended(self):
        self.assertEqual(_tier(_tns(7)), Tier.ELITE)
        self.assertEqual(_tier(_tns(13)), Tier.ASCENDED)
        self.assertEqual(_tier(replace(_tns(17), wins=0)), Tier.NOVICE)

    def test_tns_redemption_bracket_does_not_count(self):
        self.assertEqual(_tier(replace(_tns(1, event_name="Redemption Bracket"), wins=0)), Tier.NOVICE)

    def test_midweek_melting_win_with_24_is_elite_any_year(self):
        self.assertEqual(_tier(_midweek(1, placement=1, num_entrants=24, start_at=_2023)), Tier.ELITE)

    def test_midweek_melting_win_with_23_is_only_ascended(self):
        self.assertEqual(_tier(_midweek(1, placement=1, num_entrants=23)), Tier.ASCENDED)

    def test_midweek_melting_top_4_with_20_from_2024_is_ascended(self):
        self.assertEqual(_tier(_midweek(1, placement=4, num_entrants=20)), Tier.ASCENDED)

    def test_midweek_melting_top_4_before_2024_or_under_20_does_not_count(self):
        self.assertEqual(_tier(_midweek(1, placement=3, num_entrants=30, start_at=_2023)), Tier.NOVICE)
        self.assertEqual(_tier(_midweek(1, placement=3, num_entrants=19)), Tier.NOVICE)

    def test_similarly_named_series_does_not_count(self):
        peakweek = _result(placement=1, num_entrants=24, wins=0,
                           tournament_name="Peakweek Melting - Global MBAACC Netplay Event", event_name="Peakweek Global Melty")
        self.assertEqual(_tier(peakweek), Tier.NOVICE)

    def test_melt_your_blood_win_is_ascended(self):
        self.assertEqual(_tier(_melt_your_blood(1, placement=1)), Tier.ASCENDED)

    def test_melt_your_blood_top_3_needs_two_events(self):
        self.assertEqual(_tier(replace(_melt_your_blood(1, placement=2), wins=0)), Tier.NOVICE)
        self.assertEqual(_tier(_melt_your_blood(1, placement=2), _melt_your_blood(2, placement=3)), Tier.ASCENDED)


class TestRolesForTier(unittest.TestCase):
    def test_elite_also_carries_ascended(self):
        self.assertEqual(rules.roles_for(Tier.ELITE), (Tier.ELITE, Tier.ASCENDED))

    def test_other_tiers_carry_only_their_own_role(self):
        for tier in (Tier.NOVICE, Tier.FIGHTER, Tier.ASCENDED):
            with self.subTest(tier=tier):
                self.assertEqual(rules.roles_for(tier), (tier,))


class TestAssessment(unittest.TestCase):
    def test_highest_tier_wins(self):
        assessment = rules.assess([_result(rules.FROSTY_2024, placement=17), _tns(5)])
        self.assertEqual(assessment.tier, Tier.ELITE)
        self.assertEqual({q.tier for q, _ in assessment.met}, {Tier.ELITE, Tier.ASCENDED})

    def test_qualifying_hits_are_most_recent_first(self):
        old = _midweek(1, placement=1, num_entrants=30, start_at=_2023)
        new = _midweek(2, placement=1, num_entrants=30, start_at=_2025)
        _, hits = rules.assess([old, new]).met[0]
        self.assertEqual([h.event_id for h in hits], [2, 1])

    def test_missing_placement_never_qualifies(self):
        self.assertEqual(_tier(_result(rules.ECLIPSE_2026, placement=None, wins=0)), Tier.NOVICE)


if __name__ == "__main__":
    unittest.main()
