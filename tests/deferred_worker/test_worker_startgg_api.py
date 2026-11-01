import unittest
from unittest.mock import Mock, patch

import requests

import commands.matchmaking.startgg_profile as src_startgg_profile
import worker_startgg_api as startgg_api

_PROFILE_INPUTS = [
    "https://www.start.gg/user/a1b2c3d4",
    "https://start.gg/user/a1b2c3d4/details",
    "start.gg/user/a1b2c3d4",
    "user/a1b2c3d4",
    "a1b2c3d4",
    "  a1b2c3d4  ",
    "https://www.start.gg/tournament/foo/event/bar",
    "not a profile",
    "",
]


def _response(data=None, *, status=200, errors=None, headers=None) -> Mock:
    body = {"data": data}
    if errors:
        body["errors"] = errors
    return Mock(ok=200 <= status < 300, status_code=status, headers=headers or {}, json=Mock(return_value=body))


def _event_node(event_id: int, *, entrant=True, placement=3, record=None) -> dict:
    return {
        "id": event_id,
        "name": "MBAACC Singles",
        "numEntrants": 40,
        "startAt": 1700000000,
        "tournament": {"name": f"Tournament {event_id}"},
        "userEntrant": {
            "id": 9000 + event_id,
            "standing": {"placement": placement, "setRecordWithoutByes": record or {"wins": 3, "losses": 2}},
        } if entrant else None,
    }


def _events_page(nodes: list, total_pages: int) -> dict:
    return {"user": {"events": {"pageInfo": {"totalPages": total_pages}, "nodes": nodes}}}


class TestParseProfileSlug(unittest.TestCase):
    def test_accepts_urls_slugs_and_bare_ids(self):
        for value in _PROFILE_INPUTS[:6]:
            with self.subTest(value=value):
                self.assertEqual(startgg_api.parse_profile_slug(value), "user/a1b2c3d4")

    def test_rejects_non_profiles(self):
        for value in _PROFILE_INPUTS[6:]:
            with self.subTest(value=value):
                self.assertIsNone(startgg_api.parse_profile_slug(value))

    def test_matches_the_src_mirror(self):
        # MIRROR: src/commands/matchmaking/startgg_profile.py validates the same input inline.
        for value in _PROFILE_INPUTS:
            with self.subTest(value=value):
                self.assertEqual(startgg_api.parse_profile_slug(value), src_startgg_profile.parse_profile_slug(value))


class _ApiTestBase(unittest.TestCase):
    def setUp(self):
        key_patcher = patch.object(startgg_api.constants, "get_startgg_api_key", return_value="test-key")
        key_patcher.start()
        self.addCleanup(key_patcher.stop)
        post_patcher = patch.object(startgg_api.requests, "post")
        self.mock_post = post_patcher.start()
        self.addCleanup(post_patcher.stop)
        sleep_patcher = patch.object(startgg_api, "_sleep")
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)


class TestStartggApi(_ApiTestBase):
    def test_fetch_user_returns_linked_discord_ids(self):
        self.mock_post.return_value = _response({"user": {
            "id": 42, "slug": "user/abc", "player": {"gamerTag": "Tag"},
            "authorizations": [{"externalId": "123"}, None],
        }})
        user = startgg_api.fetch_user("user/abc")
        self.assertEqual((user.id, user.slug, user.discord_ids, user.gamer_tag), (42, "user/abc", ["123"], "Tag"))
        self.assertEqual(self.mock_post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_fetch_user_returns_none_for_unknown_slug(self):
        self.mock_post.return_value = _response({"user": None})
        self.assertIsNone(startgg_api.fetch_user("user/missing"))

    def test_results_paginate_dedupe_and_skip_events_without_an_entrant(self):
        self.mock_post.side_effect = [
            _response(_events_page([_event_node(1), _event_node(2, entrant=False)], total_pages=2)),
            _response(_events_page([_event_node(1), _event_node(3, record={"wins": 0, "losses": 2})], total_pages=2)),
        ]
        results = {r.event_id: r for r in startgg_api.fetch_mbaacc_results("user/abc", 42)}

        self.assertEqual(set(results), {1, 3})
        self.assertEqual((results[1].placement, results[1].wins, results[1].losses), (3, 3, 2))
        self.assertEqual(results[1].entrant_id, 9001)
        self.assertEqual(results[3].wins, 0)
        variables = self.mock_post.call_args_list[0].kwargs["json"]["variables"]
        self.assertEqual((variables["videogameId"], variables["userId"]), (startgg_api.MBAACC_VIDEOGAME_ID, 42))

    def test_missing_set_record_counts_as_no_wins(self):
        node = _event_node(1)
        node["userEntrant"]["standing"] = None
        self.mock_post.return_value = _response(_events_page([node], total_pages=1))
        (result,) = startgg_api.fetch_mbaacc_results("user/abc", 42)
        self.assertEqual((result.placement, result.wins, result.losses), (None, 0, 0))

    def test_phase_group_placements_by_entrant(self):
        self.mock_post.return_value = _response({"phaseGroup": {"standings": {"nodes": [
            {"placement": 1, "entrant": {"id": 11}},
            {"placement": 7, "entrant": {"id": 22}},
        ]}}})
        self.assertEqual(startgg_api.fetch_phase_group_placements(3151359), {11: 1, 22: 7})



class TestRetries(_ApiTestBase):
    _OK = {"user": {"id": 42, "slug": "user/abc", "authorizations": []}}

    def test_transient_failure_then_success_is_retried(self):
        transient = [
            _response(status=429),
            _response(status=502),
            _response({"user": None}, errors=[{"message": "Rate limit exceeded - api-token"}]),
            requests.ConnectionError("down"),
            requests.Timeout("slow"),
        ]
        for failure in transient:
            with self.subTest(failure=failure):
                self.mock_post.reset_mock()
                self.mock_sleep.reset_mock()
                self.mock_post.side_effect = [failure, _response(self._OK)]
                self.assertEqual(startgg_api.fetch_user("user/abc").id, 42)
                self.assertEqual(self.mock_post.call_count, 2)
                self.mock_sleep.assert_called_once_with(1)

    def test_at_most_three_tries_then_unavailable(self):
        self.mock_post.side_effect = [_response(status=429)] * 5
        with self.assertRaises(startgg_api.StartggUnavailableError):
            startgg_api.fetch_user("user/abc")
        self.assertEqual(self.mock_post.call_count, 3)
        self.assertEqual([c.args[0] for c in self.mock_sleep.call_args_list], [1, 2])

    def test_retry_after_header_is_honored_and_capped(self):
        for header, expected_wait in (("5", 5), ("120", 30)):
            with self.subTest(retry_after=header):
                self.mock_post.reset_mock()
                self.mock_sleep.reset_mock()
                self.mock_post.side_effect = [_response(status=429, headers={"Retry-After": header}), _response(self._OK)]
                startgg_api.fetch_user("user/abc")
                self.mock_sleep.assert_called_once_with(expected_wait)

    def test_permanent_failures_are_not_retried(self):
        permanent = [
            _response(status=400),
            _response(status=401),
            _response({"user": None}, errors=[{"message": "Field 'foo' doesn't exist on type 'User'"}]),
        ]
        for failure in permanent:
            with self.subTest(failure=failure):
                self.mock_post.reset_mock()
                self.mock_post.side_effect = [failure, _response(self._OK)]
                with self.assertRaises(startgg_api.StartggUnavailableError):
                    startgg_api.fetch_user("user/abc")
                self.assertEqual(self.mock_post.call_count, 1)
        self.mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
