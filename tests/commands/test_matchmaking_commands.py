import json
import unittest
from unittest.mock import Mock, patch

import commands.matchmaking.matchmaking_commands as matchmaking_commands
import commands.models.message_flags as message_flags
import utils.bot_messages as bot_messages
from commands.models.discord_event import DiscordEvent


def _make_event(command_name: str, profile: str | None = None, in_server: bool = True,
                role: str | None = None) -> DiscordEvent:
    body = {
        "application_id": "999",
        "token": "interaction-token",
        "data": {"name": command_name, "options": []},
    }
    if profile is not None:
        body["data"]["options"].append({"name": "startgg_discriminator", "type": 3, "value": profile})
    if role is not None:
        body["data"]["options"].append({"name": "role", "type": 3, "value": role})
    if in_server:
        body["guild_id"] = "123"
        body["member"] = {"user": {"id": "555"}, "roles": []}
    else:
        body["user"] = {"id": "555"}
    return DiscordEvent(body)


def _dispatched(aws_services: Mock) -> dict:
    return json.loads(aws_services.deferred_worker_sqs_queue.send_message.call_args.kwargs["MessageBody"])


class TestDeferredMatchmakingCommands(unittest.TestCase):
    def test_request_with_profile_enqueues_and_answers_ephemerally(self):
        aws_services = Mock()
        event = _make_event("request-matchmaking-role", "https://www.start.gg/user/abc123")

        response = matchmaking_commands.request_matchmaking_role(event, aws_services)

        self.assertEqual(response.content, bot_messages.CHECKING_AND_ASSIGNING)
        self.assertTrue(response.flags & message_flags.EPHEMERAL)
        sent = _dispatched(aws_services)
        self.assertEqual(sent["command_name"], "request-matchmaking-role")
        self.assertEqual(sent["event_body"], event.event_body)

    def test_request_without_a_discriminator_is_rejected_inline(self):
        aws_services = Mock()
        response = matchmaking_commands.request_matchmaking_role(_make_event("request-matchmaking-role"), aws_services)
        self.assertEqual(response.content, bot_messages.INVALID_STARTGG_PROFILE)
        aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()

    def test_bad_profile_is_rejected_inline(self):
        for command in (matchmaking_commands.request_matchmaking_role, matchmaking_commands.results_view):
            with self.subTest(command=command.__name__):
                aws_services = Mock()
                response = command(_make_event("x", "not a profile"), aws_services)
                self.assertEqual(response.content, bot_messages.INVALID_STARTGG_PROFILE)
                aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()

    def test_remove_get_fighter_and_results_view_enqueue(self):
        cases = [
            (matchmaking_commands.remove_matchmaking_role, "remove-matchmaking-role", None, "elite"),
            (matchmaking_commands.get_fighter_role, "get-fighter-role", None, None),
            (matchmaking_commands.results_view, "results-view", "user/abc123", None),
        ]
        for command, name, profile, role in cases:
            with self.subTest(command=name):
                aws_services = Mock()
                command(_make_event(name, profile, role=role), aws_services)
                self.assertEqual(_dispatched(aws_services)["command_name"], name)

    def test_remove_with_an_unknown_role_is_rejected_inline(self):
        for role in (None, "grandmaster"):
            with self.subTest(role=role):
                aws_services = Mock()
                event = _make_event("remove-matchmaking-role", role=role)
                response = matchmaking_commands.remove_matchmaking_role(event, aws_services)
                self.assertEqual(response.content, bot_messages.UNKNOWN_ROLE)
                aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()

    def test_outside_a_server_nothing_is_enqueued(self):
        commands = (
            matchmaking_commands.request_matchmaking_role,
            matchmaking_commands.remove_matchmaking_role,
            matchmaking_commands.results_view,
            matchmaking_commands.get_fighter_role,
        )
        for command in commands:
            with self.subTest(command=command.__name__):
                aws_services = Mock()
                response = command(_make_event("x", "user/abc123", in_server=False), aws_services)
                self.assertEqual(response.content, bot_messages.SERVER_ONLY)
                aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()


class TestHelp(unittest.TestCase):
    def test_help_startgg_explains_the_discriminator_and_discord_connection(self):
        aws_services = Mock()
        response = matchmaking_commands.help_startgg(_make_event("help-startgg"), aws_services)

        self.assertIn("start.gg/user/", response.content)
        self.assertIn('Remember to click "Save" after.', response.content)
        self.assertTrue(response.flags & message_flags.EPHEMERAL)
        aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()

    def test_help_commands_mentions_fighter_silently(self):
        with patch.object(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", {"fighter": "102"}):
            response = matchmaking_commands.help_commands(_make_event("help-commands"), Mock())

        self.assertIn("`/get-fighter-role` - <@&102> is available for everyone", response.content)
        self.assertEqual(response.allowed_mentions, {"parse": []})
        self.assertTrue(response.flags & message_flags.SUPPRESS_NOTIFICATIONS)
        self.assertTrue(response.flags & message_flags.EPHEMERAL)

    def test_help_commands_without_role_ids_names_fighter_in_bold(self):
        with patch.object(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", {}):
            response = matchmaking_commands.help_commands(_make_event("help-commands"), Mock())
        self.assertIn("**Fighter** is available for everyone", response.content)

    def test_help_commands_lists_every_matchmaking_command(self):
        import commands.matchmaking.mapping as mapping
        content = matchmaking_commands.help_commands(_make_event("help-commands"), Mock()).content
        for name in mapping.matchmaking_commands_mapping:
            if name not in ("help-commands", "help"):
                with self.subTest(command=name):
                    self.assertIn(f"`/{name}`", content)

    def test_help_explains_each_tier_with_silent_role_mentions(self):
        ids = {"novice": "101", "fighter": "102", "ascended": "103", "elite": "104"}
        with patch.object(matchmaking_commands.constants, "MATCHMAKING_ROLE_IDS", ids):
            response = matchmaking_commands.help_overview(_make_event("help"), Mock())

        self.assertEqual(response.content, "\n".join([
            "Use `/request-matchmaking-role` to get a pingable matchmaking role based on your start.gg tournament results.",
            "To ascend from <@&101>, you must achieve a result of 2-2 or better in a tournament with 24+ entrants.",
            "To reach <@&103>, you must ascend from the [Melt Your Blood](https://start.gg/meltyourblood) series.",
            "To become <@&104>, you must reach the top cut of a stacked, highly-competitive tournament "
            "(e.g. Top 12 at CoN 2025, Top 4 CB 2026, requirements vary per event).",
        ]))
        self.assertEqual(response.allowed_mentions, {"parse": []})
        self.assertTrue(response.flags & message_flags.SUPPRESS_NOTIFICATIONS)
        self.assertTrue(response.flags & message_flags.SUPPRESS_EMBEDS)
        self.assertTrue(response.flags & message_flags.EPHEMERAL)

    def test_invalid_discriminator_reply_points_to_help_startgg(self):
        self.assertIn("/help-startgg", bot_messages.INVALID_STARTGG_PROFILE)

    def test_no_contractions_or_leading_emoji(self):
        texts = [v for k, v in vars(bot_messages).items() if k.isupper() and isinstance(v, str)]
        for text in texts:
            if text is bot_messages.REQUIRE_MANAGE_SERVER:  # template message, not matchmaking
                continue
            with self.subTest(text=text[:40]):
                self.assertNotRegex(text, r"\b\w+n't\b|\b(It|You|I|That)'(s|re|m|ll)\b")
                self.assertTrue(text[:1].isascii())


class TestAppeal(unittest.TestCase):
    def test_points_the_user_to_enpicie_without_enqueuing(self):
        aws_services = Mock()
        response = matchmaking_commands.appeal_matchmaking_role(_make_event("appeal-matchmaking-role"), aws_services)

        self.assertIn("please DM @enpicie with supporting results", response.content)
        self.assertTrue(response.flags & message_flags.EPHEMERAL)
        aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
