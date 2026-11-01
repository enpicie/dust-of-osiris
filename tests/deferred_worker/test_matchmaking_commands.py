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
_NOVICE, _FIGHTER, _ASCENDED, _ELITE = "<@&101>", "<@&102>", "<@&103>", "<@&104>"
_NOVICE_CHANNEL = "1372597783273537607"
_DISCORD_USER = "555"
_OTHER_ROLE = "999"  # a non-matchmaking role the member holds; must never be touched


def _event_body(profile: str | None = "user/abc", roles: list | None = None, role: str | None = None) -> dict:
    options = [{"name": "startgg_discriminator", "type": 3, "value": profile}] if profile is not None else []
    if role is not None:
        options.append({"name": "role", "type": 3, "value": role})
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


_FIGHTER_RESULT = _result(1, placement=9, num_entrants=40, wins=3, tournament_name="Weekly A")
_ASCENDED_RESULT = _result(rules.ECLIPSE_2026, placement=25, tournament_name="Eclipse [1st Cour]")
_ELITE_RESULT = _result(rules.ECLIPSE_2026, placement=5, tournament_name="Eclipse [1st Cour]")
_SMALL_RESULT = _result(2, placement=5, num_entrants=8, wins=1, tournament_name="Tiny Weekly")


class _Base(unittest.TestCase):
    def setUp(self):
        self.startgg = self._patch(matchmaking_commands, "startgg_api")
        self.startgg.parse_profile_slug.side_effect = lambda value: "user/abc" if value else None
        self.startgg.fetch_user.return_value = StartggUser(id=42, slug="user/abc", discord_ids=[_DISCORD_USER])
        self.startgg.fetch_mbaacc_results.return_value = []
        self.roles = self._patch(matchmaking_commands, "discord_roles")
        self._patch(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", dict(_ROLE_IDS))
        self._patch(matchmaking_commands.constants, "NOVICE_CHANNEL_ID", _NOVICE_CHANNEL)

    def _patch(self, target, attribute, new=None):
        patcher = patch.object(target, attribute, new) if new is not None else patch.object(target, attribute)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def _added(self) -> list[str]:
        return [c.args[2] for c in self.roles.add_member_role.call_args_list]

    def _removed(self) -> list[str]:
        return [c.args[2] for c in self.roles.remove_member_role.call_args_list]

    def _request(self, results=None, roles=None, profile="user/abc") -> str:
        if results is not None:
            self.startgg.fetch_mbaacc_results.return_value = results
        reply = matchmaking_commands.handle_request_role(_event_body(profile=profile, roles=roles), Mock())
        self.assert_ephemeral_and_silent(reply)
        return reply["content"]

    def assert_ephemeral_and_silent(self, reply: dict):
        # Role mentions render, but nobody is pinged or notified.
        self.assertEqual(reply["allowed_mentions"], {"parse": []})
        self.assertTrue(reply["flags"] & matchmaking_commands.EPHEMERAL)
        self.assertTrue(reply["flags"] & matchmaking_commands.SUPPRESS_NOTIFICATIONS)
        # start.gg links (Melt Your Blood, profile) never unfurl into previews.
        self.assertTrue(reply["flags"] & matchmaking_commands.SUPPRESS_EMBEDS)


class TestRequestRoleChanges(_Base):
    def test_elite_gets_both_elite_and_ascended(self):
        self._request([_ELITE_RESULT])
        self.assertEqual((self._added(), self._removed()), (["104", "103"], []))

    def test_ascended_moving_up_to_elite_keeps_ascended(self):
        self._request([_ELITE_RESULT], roles=["103"])
        self.assertEqual((self._added(), self._removed()), (["104"], []))

    def test_lower_result_never_replaces_a_higher_role(self):
        cases = [
            ("elite, results say ascended", ["103", "104"], [_ASCENDED_RESULT], _ASCENDED),
            ("elite, results say novice", ["103", "104"], [], _NOVICE),
            ("ascended, results say fighter", ["103"], [_FIGHTER_RESULT], _FIGHTER),
        ]
        for name, roles, results, pointed_to in cases:
            with self.subTest(case=name):
                self.roles.reset_mock()
                content = self._request(results, roles=roles)
                self.assertEqual((self._added(), self._removed()), ([], []))
                self.assertIn(f"Your results point to {pointed_to}. Some results may be missing", content)

    def test_moving_up_removes_novice_but_never_other_roles(self):
        cases = [([_FIGHTER_RESULT], ["102"]), ([_ASCENDED_RESULT], ["103"]), ([_ELITE_RESULT], ["104", "103"])]
        for results, expected_added in cases:
            with self.subTest(added=expected_added):
                self.roles.reset_mock()
                self._request(results, roles=[_OTHER_ROLE, "101"])
                self.assertEqual((self._added(), self._removed()), (expected_added, ["101"]))

    def test_opted_in_fighter_does_not_block_getting_novice(self):
        self._request([], roles=["102"])
        self.assertEqual((self._added(), self._removed()), (["101"], []))

    def test_tier_request_never_removes_fighter(self):
        for results, expected_added in (([], ["101"]), ([_ELITE_RESULT], ["104", "103"])):
            with self.subTest(added=expected_added):
                self.roles.reset_mock()
                self._request(results, roles=["102"])
                self.assertEqual((self._added(), self._removed()), (expected_added, []))

    def test_unverified_discriminator_adds_fighter_and_keeps_other_roles(self):
        cases = [
            ("not linked", StartggUser(id=42, slug="user/abc", discord_ids=[]), messages.STARTGG_NOT_LINKED),
            ("someone else", StartggUser(id=42, slug="user/abc", discord_ids=["x"]), messages.STARTGG_LINKED_TO_SOMEONE_ELSE),
            ("no such profile", None, messages.STARTGG_PROFILE_NOT_FOUND),
        ]
        for name, user, reason in cases:
            with self.subTest(case=name):
                self.roles.reset_mock()
                self.startgg.fetch_mbaacc_results.reset_mock()
                self.startgg.fetch_user.return_value = user
                content = self._request(roles=["103", "104"])
                self.startgg.fetch_mbaacc_results.assert_not_called()
                self.assertEqual((self._added(), self._removed()), (["102"], []))
                self.assertTrue(content.startswith(f"You now have the {_FIGHTER} matchmaking role."))
                self.assertIn(reason, content)
                self.assertIn("make it visible on your profile", content)

    def test_unreadable_discriminator_defaults_to_fighter_without_calling_startgg(self):
        self._request(profile="")
        self.startgg.fetch_user.assert_not_called()
        self.assertEqual(self._added(), ["102"])

    def test_unset_role_ids_change_no_roles(self):
        self._patch(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", dict(_UNSET_ROLE_IDS))
        content = self._request([_ELITE_RESULT], roles=["101"])
        self.assertEqual((self._added(), self._removed()), ([], []))
        self.assertIn("would get the **Elite** and **Ascended** matchmaking roles", content)

    def test_startgg_outage_changes_no_roles(self):
        self.startgg.fetch_user.side_effect = StartggUnavailableError()
        self.assertEqual(self._request(), messages.STARTGG_UNAVAILABLE)
        self.assertEqual((self._added(), self._removed()), ([], []))

    def test_discord_refusal_is_reported(self):
        self.roles.add_member_role.side_effect = RoleUpdateError("HTTP 403")
        self.assertEqual(self._request(), messages.ROLE_UPDATE_FAILED)

    def test_failed_add_removes_nothing(self):
        self.roles.add_member_role.side_effect = RoleUpdateError("HTTP 403")
        self._request([_ASCENDED_RESULT], roles=["101"])  # novice -> ascended
        self.roles.add_member_role.assert_called_once_with("777", _DISCORD_USER, "103")
        self.roles.remove_member_role.assert_not_called()


class TestRequestRoleWording(_Base):
    def test_novice_with_results(self):
        self.assertEqual(self._request([_SMALL_RESULT]), "\n".join([
            f"You now have the {_NOVICE} matchmaking role.",
            messages.TIER_HINTS["novice"],
            f"{_FIGHTER} is also available to everyone as the general looking-for-games role.",
        ]))

    def test_novice_with_no_results_points_to_the_novice_channel(self):
        self.assertEqual(self._request([]), "\n".join([
            f"You now have the {_NOVICE} matchmaking role.",
            f"Found 0 MBAACC results for your profile. Ping {_NOVICE} in <#{_NOVICE_CHANNEL}> to request "
            "matches with other new players.",
            messages.TIER_HINTS["novice"],
            f"{_FIGHTER} is also available to everyone as the general looking-for-games role.",
        ]))

    def test_fighter_from_results_shows_the_qualifying_result_and_no_fighter_reminder(self):
        content = self._request([_FIGHTER_RESULT])
        self.assertEqual(content, "\n".join([
            f"You now have the {_FIGHTER} matchmaking role.",
            "Qualifying result: 9th of 40 at Weekly A (3-2, 2023-11-14).",
        ]))

    def test_elite_mentions_both_roles_and_the_qualifying_result(self):
        self.assertEqual(self._request([_ELITE_RESULT]), "\n".join([
            f"You now have the {_ELITE} and {_ASCENDED} matchmaking roles.",
            "Qualifying result: 5th of 100 at Eclipse [1st Cour] (0-2, 2023-11-14).",
            f"{_FIGHTER} is also available to everyone as the general looking-for-games role.",
        ]))

    def test_ascended_points_to_melt_your_blood_instead_of_results(self):
        self.assertEqual(self._request([_ASCENDED_RESULT]), "\n".join([
            f"You now have the {_ASCENDED} matchmaking role.",
            "Ascended is the same bar as ascending from the [Melt Your Blood](https://start.gg/meltyourblood) series.",
            f"{_FIGHTER} is also available to everyone as the general looking-for-games role.",
        ]))

    def test_qualifying_result_names_the_midweek_melting_edition(self):
        midweek = _result(5, placement=1, num_entrants=30, tournament_name="Midweek Melting 40")
        self.assertIn("1st of 30 at Midweek Melting 40", self._request([midweek]))

    def test_already_held_gives_the_tier_hint(self):
        cases = [
            ([_SMALL_RESULT], ["101"], "novice", f"You already have the {_NOVICE} matchmaking role."),
            ([_FIGHTER_RESULT], ["102"], "fighter", f"You already have the {_FIGHTER} matchmaking role."),
            ([_ASCENDED_RESULT], ["103"], "ascended", f"You already have the {_ASCENDED} matchmaking role."),
            ([_ELITE_RESULT], ["103", "104"], "elite", f"You already have the {_ELITE} and {_ASCENDED} matchmaking roles."),
        ]
        for results, roles, tier, headline in cases:
            with self.subTest(tier=tier):
                self.roles.reset_mock()
                content = self._request(results, roles=roles)
                self.assertEqual((self._added(), self._removed()), ([], []))
                lines = content.split("\n")
                self.assertEqual(lines[:2], [headline, messages.TIER_HINTS[tier]])

    def test_no_leading_emoji_or_appeal_line(self):
        for results in ([], [_FIGHTER_RESULT], [_ASCENDED_RESULT], [_ELITE_RESULT]):
            with self.subTest(results=results):
                self.roles.reset_mock()
                content = self._request(results)
                self.assertTrue(content.startswith("You now have"))
                self.assertNotIn("appeal", content)


class TestPlacementOverride(_Base):
    def test_frosty_2026_uses_top_8_bracket_placement(self):
        frosty = _result(rules.FROSTY_2026, placement=1)  # event-level standings say 1st
        self.startgg.fetch_mbaacc_results.return_value = [frosty]
        self.startgg.fetch_phase_group_placements.return_value = {frosty.entrant_id: 7}
        content = self._request()
        self.startgg.fetch_phase_group_placements.assert_called_once_with(3151359)
        self.assertIn("7th of 100", content)

    def test_frosty_2026_entrant_outside_top_8_has_no_placement(self):
        self.startgg.fetch_phase_group_placements.return_value = {}
        content = self._request([_result(rules.FROSTY_2026, placement=1)])
        self.roles.add_member_role.assert_called_once_with("777", _DISCORD_USER, "101")  # novice
        self.assertIn(_NOVICE, content)


class TestRemoveRole(_Base):
    def _remove(self, role: str, roles: list) -> dict:
        reply = matchmaking_commands.handle_remove_role(_event_body(profile=None, roles=roles, role=role), Mock())
        self.assert_ephemeral_and_silent(reply)
        return reply

    def test_removes_exactly_the_named_role(self):
        for role, role_id in (("novice", "101"), ("fighter", "102"), ("ascended", "103"), ("elite", "104")):
            with self.subTest(role=role):
                self.roles.reset_mock()
                reply = self._remove(role, [_OTHER_ROLE, "101", "102", "103", "104"])
                self.roles.remove_member_role.assert_called_once_with("777", _DISCORD_USER, role_id)
                self.assertEqual(reply["content"], f"Removed your <@&{role_id}> matchmaking role.")

    def test_elite_player_can_drop_ascended_and_keep_elite(self):
        self._remove("ascended", ["103", "104"])
        self.roles.remove_member_role.assert_called_once_with("777", _DISCORD_USER, "103")

    def test_role_not_held(self):
        reply = self._remove("elite", ["103"])
        self.roles.remove_member_role.assert_not_called()
        self.assertEqual(reply["content"], f"You do not have the {_ELITE} matchmaking role.")

    def test_unknown_role(self):
        reply = self._remove("grandmaster", ["101"])
        self.roles.remove_member_role.assert_not_called()
        self.assertEqual(reply["content"], messages.UNKNOWN_ROLE)

    def test_unset_role_ids_remove_nothing(self):
        self._patch(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", dict(_UNSET_ROLE_IDS))
        self._remove("novice", ["ROLE_ID_PLACEHOLDER"])
        self.roles.remove_member_role.assert_not_called()

    def test_discord_refusal_is_reported(self):
        self.roles.remove_member_role.side_effect = RoleUpdateError("HTTP 403")
        self.assertEqual(self._remove("novice", ["101"])["content"], messages.ROLE_UPDATE_FAILED)


class TestGetFighterRole(_Base):
    def _get(self, roles: list) -> str:
        reply = matchmaking_commands.handle_get_fighter_role(_event_body(profile=None, roles=roles), Mock())
        self.assert_ephemeral_and_silent(reply)
        return reply["content"]

    def test_adds_only_fighter(self):
        content = self._get(["103", "104"])
        self.roles.add_member_role.assert_called_once_with("777", _DISCORD_USER, "102")
        self.roles.remove_member_role.assert_not_called()
        self.startgg.fetch_user.assert_not_called()
        self.assertEqual(content, f"You now have the {_FIGHTER} matchmaking role.")

    def test_already_held(self):
        self.assertEqual(self._get(["102"]), f"You already have the {_FIGHTER} matchmaking role.")
        self.roles.add_member_role.assert_not_called()

    def test_unset_role_ids_change_nothing(self):
        self._patch(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", dict(_UNSET_ROLE_IDS))
        self._get([])
        self.roles.add_member_role.assert_not_called()


class TestResultsView(_Base):
    def _view(self, results=None) -> dict:
        if results is not None:
            self.startgg.fetch_mbaacc_results.return_value = results
        reply = matchmaking_commands.handle_results_view(_event_body(), Mock())
        self.assert_ephemeral_and_silent(reply)
        return reply

    def test_elite_lists_its_qualifying_results_under_the_profile_link(self):
        cb = _result(rules.COMBO_BREAKER_2026, placement=3, tournament_name="COMBO BREAKER 2026", start_at=1700000000)
        eclipse = _result(rules.ECLIPSE_2026, placement=1, tournament_name="Eclipse [1st Cour]", start_at=1800000000)
        content = self._view([cb, eclipse, _SMALL_RESULT])["content"]

        self.assertEqual(content, "\n".join([
            "**Matchmaking results for user/abc** (start.gg `user/abc`)",
            f"Your results point to the {_ELITE} and {_ASCENDED} matchmaking roles. Checked 3 MBAACC events.",
            "**[Qualifying results](https://www.start.gg/user/abc)**",
            "• 1st of 100 at Eclipse [1st Cour] (0-2, 2027-01-15)",   # most recent first, each event once
            "• 3rd of 100 at COMBO BREAKER 2026 (0-2, 2023-11-14)",
        ]))
        self.roles.add_member_role.assert_not_called()

    def test_ascended_points_to_melt_your_blood_instead_of_listing_results(self):
        content = self._view([_ASCENDED_RESULT, _SMALL_RESULT])["content"]
        self.assertEqual(content, "\n".join([
            "**Matchmaking results for user/abc** (start.gg `user/abc`)",
            f"Your results point to the {_ASCENDED} matchmaking role. Checked 2 MBAACC events.",
            "Ascended is the same bar as ascending from the [Melt Your Blood](https://start.gg/meltyourblood) series.",
        ]))

    def test_fighter_lists_at_most_five_results(self):
        results = [_result(10 + i, placement=9, num_entrants=40, wins=2, tournament_name=f"Weekly {i}",
                           start_at=1700000000 + i) for i in range(8)]
        content = self._view(results)["content"]
        self.assertEqual(content.count("\n• "), 5)
        self.assertIn("Weekly 7", content)   # newest kept
        self.assertNotIn("Weekly 0", content)

    def test_uses_the_gamer_tag_when_start_gg_has_one(self):
        self.startgg.fetch_user.return_value = StartggUser(id=42, slug="user/abc", discord_ids=[_DISCORD_USER], gamer_tag="Tag")
        self.assertTrue(self._view([_FIGHTER_RESULT])["content"].startswith("**Matchmaking results for Tag**"))

    def test_novice_gets_the_hint_instead_of_results(self):
        content = self._view([_SMALL_RESULT])["content"]
        self.assertIn(f"Your results point to the {_NOVICE} matchmaking role. Checked 1 MBAACC event.", content)
        self.assertTrue(content.endswith(messages.TIER_HINTS["novice"]))
        self.assertNotIn("Qualifying results", content)

    def test_no_results_points_to_the_novice_channel(self):
        content = self._view([])["content"]
        self.assertNotIn("Checked", content)
        self.assertIn(f"Ping {_NOVICE} in <#{_NOVICE_CHANNEL}>", content)
        self.assertTrue(content.endswith(messages.TIER_HINTS["novice"]))

    def test_unverified_profile_is_refused_with_link_guidance_and_no_role_changes(self):
        self.startgg.fetch_user.return_value = StartggUser(id=42, slug="user/abc", discord_ids=[])
        content = self._view()["content"]
        self.assertEqual(content, messages.STARTGG_NOT_LINKED + messages.LINK_DISCORD_TO_STARTGG)
        self.roles.add_member_role.assert_not_called()


class TestNoContractionsOrLeadingEmoji(unittest.TestCase):
    def test_worker_messages(self):
        texts = [v for k, v in vars(messages).items() if k.isupper() and isinstance(v, str)]
        texts += list(messages.TIER_HINTS.values())
        for text in texts:
            with self.subTest(text=text[:40]):
                self.assertNotRegex(text, r"\b\w+n't\b|\b(It|You|I|That)'(s|re|m|ll)\b")
                self.assertTrue(text.lstrip("\n")[:1].isascii())


if __name__ == "__main__":
    unittest.main()
