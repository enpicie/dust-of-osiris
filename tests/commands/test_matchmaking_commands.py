import json
import unittest
from unittest.mock import Mock

import commands.matchmaking.matchmaking_commands as matchmaking_commands
import commands.models.message_flags as message_flags
import utils.bot_messages as bot_messages
from commands.models.discord_event import DiscordEvent


def _make_event(command_name: str, profile: str | None = None, in_server: bool = True) -> DiscordEvent:
    body = {
        "application_id": "999",
        "token": "interaction-token",
        "data": {"name": command_name, "options": []},
    }
    if profile is not None:
        body["data"]["options"].append({"name": "startgg_discriminator", "type": 3, "value": profile})
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

        self.assertTrue(response.content.startswith("⏳"))
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

    def test_remove_and_results_view_enqueue(self):
        cases = [
            (matchmaking_commands.remove_matchmaking_role, "remove-matchmaking-role", None),
            (matchmaking_commands.get_fighter_role, "get-fighter-role", None),
            (matchmaking_commands.remove_fighter_role, "remove-fighter-role", None),
            (matchmaking_commands.results_view, "results-view", "user/abc123"),
        ]
        for command, name, profile in cases:
            with self.subTest(command=name):
                aws_services = Mock()
                command(_make_event(name, profile), aws_services)
                self.assertEqual(_dispatched(aws_services)["command_name"], name)

    def test_outside_a_server_nothing_is_enqueued(self):
        commands = (
            matchmaking_commands.request_matchmaking_role,
            matchmaking_commands.remove_matchmaking_role,
            matchmaking_commands.results_view,
            matchmaking_commands.get_fighter_role,
            matchmaking_commands.remove_fighter_role,
        )
        for command in commands:
            with self.subTest(command=command.__name__):
                aws_services = Mock()
                response = command(_make_event("x", "user/abc123", in_server=False), aws_services)
                self.assertEqual(response.content, bot_messages.SERVER_ONLY)
                aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()


class TestMatchmakingHelp(unittest.TestCase):
    def test_explains_where_to_find_the_discriminator_without_enqueuing(self):
        aws_services = Mock()
        response = matchmaking_commands.matchmaking_help(_make_event("matchmaking-help"), aws_services)

        self.assertIn("discriminator", response.content)
        self.assertIn("start.gg/user/", response.content)
        self.assertLessEqual(len(response.content), 2000)
        self.assertTrue(response.flags & message_flags.EPHEMERAL)
        aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()

    def test_invalid_discriminator_reply_points_to_help(self):
        self.assertIn("/matchmaking-help", bot_messages.INVALID_STARTGG_PROFILE)


class TestAppeal(unittest.TestCase):
    def test_points_the_user_to_enpicie_without_enqueuing(self):
        aws_services = Mock()
        response = matchmaking_commands.appeal_matchmaking_role(_make_event("appeal-matchmaking-role"), aws_services)

        self.assertIn("@enpicie", response.content)
        self.assertTrue(response.flags & message_flags.EPHEMERAL)
        aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
