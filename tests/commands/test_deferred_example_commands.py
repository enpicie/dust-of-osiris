import json
import unittest
from unittest.mock import Mock

import commands.deferred_example.deferred_example_commands as deferred_example_commands
from commands.models.discord_event import DiscordEvent


def _make_event(text: str) -> DiscordEvent:
    return DiscordEvent({
        "application_id": "999",
        "token": "interaction-token",
        "guild_id": "123",
        "data": {"name": "slow-echo", "options": [{"name": "text", "type": 3, "value": text}]},
    })


class TestSlowEcho(unittest.TestCase):
    def test_enqueues_the_interaction_and_returns_placeholder(self):
        aws_services = Mock()
        event = _make_event("hello")

        response = deferred_example_commands.slow_echo(event, aws_services)

        self.assertTrue(response.content.startswith("⏳"))
        sent = json.loads(aws_services.deferred_worker_sqs_queue.send_message.call_args.kwargs["MessageBody"])
        self.assertEqual(sent["command_name"], "slow-echo")
        # The worker needs the whole body: application_id + token address the followup.
        self.assertEqual(sent["event_body"], event.event_body)

    def test_blank_text_is_rejected_inline_without_enqueuing(self):
        aws_services = Mock()
        with self.assertRaises(ValueError):
            deferred_example_commands.slow_echo(_make_event("   "), aws_services)
        aws_services.deferred_worker_sqs_queue.send_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
