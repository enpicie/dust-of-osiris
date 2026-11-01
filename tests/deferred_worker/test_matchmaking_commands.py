import unittest
from unittest.mock import Mock, patch

import matchmaking_commands
import matchmaking_rules as rules
import worker_messages as messages
from matchmaking_rules import EventResult
from worker_discord_roles import RoleUpdateError
from worker_startgg_api import StartggUnavailableError, StartggUser

_ROLE_IDS = {"novice": "101", "fighter": "102", "ascended": "103", "elite": "104"}
_UNSET_ROLE_IDS = {tier: "ROLE_ID_PLACEHOLDER" for tier in _ROLE_IDS}
_DISCORD_USER = "555"
_OTHER_ROLE = "999"  # a non-matchmaking role the member holds; must never be touched


def _event_body(profile: str | None = "user/abc", roles: list | None = None) -> dict:
    options = [{"name": "startgg_discriminator", "type": 3, "value": profile}] if profile is not None else []
    return {
        "guild_id": "777",
        "member": {"user": {"id": _DISCORD_USER}, "roles": roles if roles is not None else [_OTHER_ROLE]},
        "data": {"name": "request-matchmaking-role", "options": options},
    }


def _result(event_id: int, *, placement: int | None, num_entrants: int = 100, wins: int = 0,
            tournament_name: str = "Local", start_at: int = 1700000000) -> EventResult:
    return EventResult(event_id=event_id, event_name="MBAACC", tournament_name=tournament_name,
                       num_entrants=num_entrants, start_at=start_at, entrant_id=event_id * 10,
                       placement=placement, wins=wins, losses=2)


class _Base(unittest.TestCase):
    def setUp(self):
        self.startgg = self._patch(matchmaking_commands, "startgg_api")
        self.startgg.parse_profile_slug.side_effect = lambda value: "user/abc" if value else None
        self.startgg.fetch_user.return_value = StartggUser(id=42, slug="user/abc", discord_ids=[_DISCORD_USER])
        self.startgg.fetch_mbaacc_results.return_value = []
        self.roles = self._patch(matchmaking_commands, "discord_roles")
        self._patch(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", dict(_ROLE_IDS))

    def _patch(self, target, attribute, new=None):
        patcher = patch.object(target, attribute, new) if new is not None else patch.object(target, attribute)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def assert_ephemeral_and_silent(self, reply: dict):
        self.assertEqual(reply["flags"], matchmaking_commands.EPHEMERAL)
        self.assertEqual(reply["allowed_mentions"], {"parse": []})


class TestRequestRole(_Base):
    def _added(self) -> list[str]:
        return [c.args[2] for c in self.roles.add_member_role.call_args_list]

    def _removed(self) -> list[str]:
        return [c.args[2] for c in self.roles.remove_member_role.call_args_list]

    def test_elite_gets_both_elite_and_ascended(self):
        self.startgg.fetch_mbaacc_results.return_value = [_result(rules.ECLIPSE_2026, placement=5)]

        reply = matchmaking_commands.handle_request_role(_event_body(), Mock())

        self.assertEqual(self._added(), ["104", "103"])
        self.assertEqual(self._removed(), [])
        self.assertIn("**Elite** and **Ascended** matchmaking roles", reply["content"])
        self.assertIn("Top 8 at Eclipse 2026", reply["content"])
        self.assert_ephemeral_and_silent(reply)

    def test_elite_already_holding_ascended_only_adds_elite(self):
        self.startgg.fetch_mbaacc_results.return_value = [_result(rules.ECLIPSE_2026, placement=5)]
        matchmaking_commands.handle_request_role(_event_body(roles=["103"]), Mock())
        self.assertEqual((self._added(), self._removed()), (["104"], []))

    def test_ascended_moving_up_to_elite_keeps_ascended(self):
        self.startgg.fetch_mbaacc_results.return_value = [_result(rules.ECLIPSE_2026, placement=5)]
        matchmaking_commands.handle_request_role(_event_body(roles=["103"]), Mock())
        self.assertEqual((self._added(), self._removed()), (["104"], []))

    def test_lower_result_never_replaces_a_higher_role(self):
        cases = [
            ("elite, results say ascended", ["103", "104"], [_result(rules.ECLIPSE_2026, placement=25)], "Ascended"),
            ("elite, results say novice", ["103", "104"], [], "Novice"),
            ("ascended, results say fighter", ["103"], [_result(1, placement=9, num_entrants=40, wins=3)], "Fighter"),
            ("ascended, results say novice", ["103"], [], "Novice"),
        ]
        for name, roles, results, tier in cases:
            with self.subTest(case=name):
                self.roles.reset_mock()
                self.startgg.fetch_mbaacc_results.return_value = results
                reply = matchmaking_commands.handle_request_role(_event_body(roles=roles), Mock())
                self.assertEqual((self._added(), self._removed()), ([], []))
                self.assertIn(f"now point to **{tier}**", reply["content"])
                self.assertIn("roles only move up", reply["content"])

    def test_moving_up_removes_novice_but_never_other_roles(self):
        cases = [
            ([_result(1, placement=9, num_entrants=40, wins=3)], ["102"]),        # fighter
            ([_result(rules.ECLIPSE_2026, placement=25)], ["103"]),               # ascended
            ([_result(rules.ECLIPSE_2026, placement=5)], ["104", "103"]),         # elite
        ]
        for results, expected_added in cases:
            with self.subTest(added=expected_added):
                self.roles.reset_mock()
                self.startgg.fetch_mbaacc_results.return_value = results
                matchmaking_commands.handle_request_role(_event_body(roles=[_OTHER_ROLE, "101"]), Mock())
                self.assertEqual((self._added(), self._removed()), (expected_added, ["101"]))
                self.assertNotIn(_OTHER_ROLE, self._added() + self._removed())

    def test_opted_in_fighter_does_not_block_getting_novice(self):
        # Fighter is universal, not a level: a Novice-level player who opted in still gets Novice.
        matchmaking_commands.handle_request_role(_event_body(roles=["102"]), Mock())
        self.assertEqual((self._added(), self._removed()), (["101"], []))

    def test_already_holding_the_roles_changes_nothing(self):
        cases = [([], ["101"], "already have the **Novice** matchmaking role"),
                 ([_result(rules.ECLIPSE_2026, placement=5)], ["103", "104"], "already have the **Elite** and **Ascended**")]
        for results, roles, expected in cases:
            with self.subTest(expected=expected):
                self.roles.reset_mock()
                self.startgg.fetch_mbaacc_results.return_value = results
                reply = matchmaking_commands.handle_request_role(_event_body(roles=roles), Mock())
                self.assertEqual((self._added(), self._removed()), ([], []))
                self.assertIn(expected, reply["content"])

    def test_every_non_fighter_reply_says_anyone_can_pick_up_fighter(self):
        cases = [
            ([], "Novice"),
            ([_result(rules.ECLIPSE_2026, placement=25)], "Ascended"),
            ([_result(rules.ECLIPSE_2026, placement=5)], "Elite"),
        ]
        for results, tier in cases:
            with self.subTest(tier=tier):
                self.startgg.fetch_mbaacc_results.return_value = results
                reply = matchmaking_commands.handle_request_role(_event_body(), Mock())
                self.assertIn(f"**{tier}**", reply["content"])
                self.assertIn(messages.FIGHTER_OPEN_TO_EVERYONE.strip(), reply["content"])

    def test_fighter_reply_does_not_repeat_the_fighter_notice(self):
        self.startgg.fetch_mbaacc_results.return_value = [_result(1, placement=9, num_entrants=40, wins=3)]
        reply = matchmaking_commands.handle_request_role(_event_body(), Mock())
        self.assertNotIn(messages.FIGHTER_OPEN_TO_EVERYONE.strip(), reply["content"])

    def test_unset_role_ids_change_no_roles(self):
        self._patch(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", dict(_UNSET_ROLE_IDS))
        self.startgg.fetch_mbaacc_results.return_value = [_result(rules.ECLIPSE_2026, placement=5)]

        reply = matchmaking_commands.handle_request_role(_event_body(roles=["101"]), Mock())

        self.assertEqual((self._added(), self._removed()), ([], []))
        self.assertIn("would get the **Elite** and **Ascended**", reply["content"])

    def test_unverified_discriminator_adds_fighter_and_keeps_other_roles(self):
        cases = [
            ("not linked", StartggUser(id=42, slug="user/abc", discord_ids=[]), messages.STARTGG_NOT_LINKED),
            ("someone else", StartggUser(id=42, slug="user/abc", discord_ids=["someone-else"]),
             messages.STARTGG_LINKED_TO_SOMEONE_ELSE),
            ("no such profile", None, messages.STARTGG_PROFILE_NOT_FOUND),
        ]
        for name, user, reason in cases:
            with self.subTest(case=name):
                self.roles.reset_mock()
                self.startgg.fetch_mbaacc_results.reset_mock()
                self.startgg.fetch_user.return_value = user

                reply = matchmaking_commands.handle_request_role(_event_body(roles=["103", "104"]), Mock())

                self.startgg.fetch_mbaacc_results.assert_not_called()
                # Not verified, so the existing Elite + Ascended stay put.
                self.assertEqual((self._added(), self._removed()), (["102"], []))
                self.assertIn("**Fighter**", reply["content"])
                self.assertIn(reason, reply["content"])
                self.assertIn("make it visible on your profile", reply["content"])

    def test_unreadable_discriminator_defaults_to_fighter_without_calling_startgg(self):
        reply = matchmaking_commands.handle_request_role(_event_body(profile=""), Mock())

        self.startgg.fetch_user.assert_not_called()
        self.assertEqual(self._added(), ["102"])
        self.assertIn("**Fighter**", reply["content"])

    def test_tier_request_never_removes_fighter(self):
        cases = [([], ["101"]), ([_result(rules.ECLIPSE_2026, placement=5)], ["104", "103"])]
        for results, expected_added in cases:
            with self.subTest(added=expected_added):
                self.roles.reset_mock()
                self.startgg.fetch_mbaacc_results.return_value = results
                matchmaking_commands.handle_request_role(_event_body(roles=["102"]), Mock())
                self.assertEqual((self._added(), self._removed()), (expected_added, []))

    def test_startgg_outage_changes_no_roles(self):
        self.startgg.fetch_user.side_effect = StartggUnavailableError()
        reply = matchmaking_commands.handle_request_role(_event_body(), Mock())
        self.assertEqual(reply["content"], messages.STARTGG_UNAVAILABLE)
        self.assertEqual((self._added(), self._removed()), ([], []))

    def test_discord_refusal_is_reported(self):
        self.roles.add_member_role.side_effect = RoleUpdateError("HTTP 403")
        reply = matchmaking_commands.handle_request_role(_event_body(), Mock())
        self.assertEqual(reply["content"], messages.ROLE_UPDATE_FAILED)

    def test_failed_add_removes_nothing(self):
        self.roles.add_member_role.side_effect = RoleUpdateError("HTTP 403")
        self.startgg.fetch_mbaacc_results.return_value = [_result(rules.ECLIPSE_2026, placement=25)]
        matchmaking_commands.handle_request_role(_event_body(roles=["101"]), Mock())  # novice -> ascended
        self.roles.add_member_role.assert_called_once_with("777", _DISCORD_USER, "103")
        self.roles.remove_member_role.assert_not_called()


class TestPlacementOverride(_Base):
    def test_frosty_2026_uses_top_8_bracket_placement(self):
        frosty = _result(rules.FROSTY_2026, placement=1)  # event-level standings say 1st
        self.startgg.fetch_mbaacc_results.return_value = [frosty]
        self.startgg.fetch_phase_group_placements.return_value = {frosty.entrant_id: 7}

        reply = matchmaking_commands.handle_request_role(_event_body(), Mock())

        self.startgg.fetch_phase_group_placements.assert_called_once_with(3151359)
        self.assertIn("7th of 100", reply["content"])

    def test_frosty_2026_entrant_outside_top_8_has_no_placement(self):
        self.startgg.fetch_mbaacc_results.return_value = [_result(rules.FROSTY_2026, placement=1)]
        self.startgg.fetch_phase_group_placements.return_value = {}

        reply = matchmaking_commands.handle_request_role(_event_body(), Mock())

        self.roles.add_member_role.assert_called_once_with("777", _DISCORD_USER, "101")  # novice
        self.assertIn("**Novice**", reply["content"])


class TestRemoveRole(_Base):
    def test_removes_only_held_matchmaking_roles(self):
        reply = matchmaking_commands.handle_remove_role(_event_body(roles=[_OTHER_ROLE, "103"]), Mock())

        self.roles.remove_member_role.assert_called_once_with("777", _DISCORD_USER, "103")
        self.assertIn("**Ascended**", reply["content"])

    def test_keeps_fighter_and_says_how_to_drop_it(self):
        reply = matchmaking_commands.handle_remove_role(_event_body(roles=["102", "103", "104"]), Mock())

        self.assertEqual([c.args[2] for c in self.roles.remove_member_role.call_args_list], ["103", "104"])
        self.assertIn("**Ascended** and **Elite** matchmaking roles", reply["content"])
        self.assertIn("/remove-fighter-role", reply["content"])

    def test_fighter_only_counts_as_nothing_to_remove(self):
        reply = matchmaking_commands.handle_remove_role(_event_body(roles=["102"]), Mock())
        self.roles.remove_member_role.assert_not_called()
        self.assertIn(messages.NO_ROLE_TO_REMOVE, reply["content"])
        self.assertIn("/remove-fighter-role", reply["content"])

    def test_nothing_to_remove(self):
        reply = matchmaking_commands.handle_remove_role(_event_body(roles=[_OTHER_ROLE]), Mock())
        self.roles.remove_member_role.assert_not_called()
        self.assertEqual(reply["content"], messages.NO_ROLE_TO_REMOVE)

    def test_unset_role_ids_remove_nothing(self):
        self._patch(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", dict(_UNSET_ROLE_IDS))
        matchmaking_commands.handle_remove_role(_event_body(roles=["ROLE_ID_PLACEHOLDER"]), Mock())
        self.roles.remove_member_role.assert_not_called()


class TestFighterRole(_Base):
    def test_get_adds_only_fighter(self):
        reply = matchmaking_commands.handle_get_fighter_role(_event_body(profile=None, roles=["103", "104"]), Mock())

        self.roles.add_member_role.assert_called_once_with("777", _DISCORD_USER, "102")
        self.roles.remove_member_role.assert_not_called()
        self.assertIn("now have the **Fighter** matchmaking role", reply["content"])
        self.startgg.fetch_user.assert_not_called()
        self.assert_ephemeral_and_silent(reply)

    def test_get_when_already_held(self):
        reply = matchmaking_commands.handle_get_fighter_role(_event_body(profile=None, roles=["102"]), Mock())
        self.roles.add_member_role.assert_not_called()
        self.assertIn("already have the **Fighter**", reply["content"])

    def test_remove_drops_only_fighter(self):
        body = _event_body(profile=None, roles=["102", "104", _OTHER_ROLE])
        reply = matchmaking_commands.handle_remove_fighter_role(body, Mock())
        self.roles.remove_member_role.assert_called_once_with("777", _DISCORD_USER, "102")
        self.assertIn("**Fighter**", reply["content"])

    def test_remove_when_not_held(self):
        reply = matchmaking_commands.handle_remove_fighter_role(_event_body(profile=None, roles=["104"]), Mock())
        self.roles.remove_member_role.assert_not_called()
        self.assertEqual(reply["content"], messages.NO_FIGHTER_TO_REMOVE)

    def test_unset_role_ids_change_nothing(self):
        self._patch(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", dict(_UNSET_ROLE_IDS))
        matchmaking_commands.handle_get_fighter_role(_event_body(profile=None), Mock())
        matchmaking_commands.handle_remove_fighter_role(_event_body(profile=None, roles=["ROLE_ID_PLACEHOLDER"]), Mock())
        self.roles.add_member_role.assert_not_called()
        self.roles.remove_member_role.assert_not_called()


class TestResultsView(_Base):
    def test_lists_qualifying_and_other_results(self):
        self.startgg.fetch_mbaacc_results.return_value = [
            _result(rules.COMBO_BREAKER_2026, placement=25, tournament_name="COMBO BREAKER 2026"),
            _result(2, placement=9, num_entrants=30, wins=2, tournament_name="Weekly A"),
            _result(3, placement=5, num_entrants=8, wins=1, tournament_name="Weekly B"),
        ]

        reply = matchmaking_commands.handle_results_view(_event_body(), Mock())
        content = reply["content"]

        self.assertIn("Eligible role: **Ascended**", content)
        self.assertIn("Top 32 at Combo Breaker 2026", content)
        self.assertIn("25th of 100 at COMBO BREAKER 2026", content)
        self.assertIn("Weekly A", content)  # fighter-qualifying
        self.assertIn("Other results", content)
        self.assertIn("5th of 8 at Weekly B", content)
        self.roles.add_member_role.assert_not_called()
        self.assert_ephemeral_and_silent(reply)

    def test_long_histories_fit_in_one_discord_message(self):
        self.startgg.fetch_mbaacc_results.return_value = [
            _result(i, placement=40, tournament_name=f"A Long Tournament Name Number {i}", start_at=1700000000 + i)
            for i in range(1, 300)
        ]
        content = matchmaking_commands.handle_results_view(_event_body(), Mock())["content"]
        self.assertLessEqual(len(content), 2000)
        self.assertRegex(content, r"…and \d+ more\.$")

    def test_unlinked_profile_is_refused_without_changing_roles(self):
        self.startgg.fetch_user.return_value = StartggUser(id=42, slug="user/abc", discord_ids=[])
        reply = matchmaking_commands.handle_results_view(_event_body(), Mock())
        self.assertEqual(reply["content"], messages.STARTGG_NOT_LINKED)
        self.roles.add_member_role.assert_not_called()

    def test_no_results(self):
        content = matchmaking_commands.handle_results_view(_event_body(), Mock())["content"]
        self.assertIn(messages.RESULTS_NONE.strip(), content)


if __name__ == "__main__":
    unittest.main()
