import unittest
from unittest.mock import Mock, patch

import bot
import commands.command_map as command_map
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage


def _make_command_body(command_name="fake-command"):
    return {
        "type": 2,
        "guild_id": "123456789012345678",
        "channel_id": "222333444555666777",
        "data": {"name": command_name},
        "member": {"user": {"id": "111222333444555666", "username": "TestUser"}},
    }


class TestProcessBotCommand(unittest.TestCase):
    def _patch_command_map(self, mapping):
        patcher = patch.dict(command_map.command_map, mapping, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_dispatches_to_mapped_command_and_returns_response_dict(self):
        fake_command = Mock(return_value=ResponseMessage(content="fake command ran"))
        self._patch_command_map({"fake-command": {"function": fake_command, "params": []}})
        aws_services = Mock()

        response = bot.process_bot_command(_make_command_body("fake-command"), aws_services)

        fake_command.assert_called_once()
        called_event, called_services = fake_command.call_args.args
        self.assertIsInstance(called_event, DiscordEvent)
        self.assertIs(called_services, aws_services)
        self.assertEqual(response["data"]["content"], "fake command ran")
        self.assertEqual(response["type"], 4)

    def test_unknown_command_name_raises_value_error(self):
        self._patch_command_map({})
        with self.assertRaises(ValueError) as ctx:
            bot.process_bot_command(_make_command_body("not-a-command"), Mock())
        self.assertIn("No command registered for not-a-command", str(ctx.exception))

    def test_body_without_data_field_raises_key_error(self):
        with self.assertRaises(KeyError):
            bot.process_bot_command({"type": 2}, Mock())

    def test_command_raising_value_error_returns_its_message_as_response(self):
        fake_command = Mock(side_effect=ValueError("user-facing validation problem"))
        self._patch_command_map({"fake-command": {"function": fake_command, "params": []}})

        response = bot.process_bot_command(_make_command_body("fake-command"), Mock())

        self.assertEqual(response["data"]["content"], "user-facing validation problem")

    def test_command_raising_unexpected_error_returns_generic_error_response(self):
        fake_command = Mock(side_effect=RuntimeError("internal kaboom"))
        self._patch_command_map({"fake-command": {"function": fake_command, "params": []}})

        response = bot.process_bot_command(_make_command_body("fake-command"), Mock())

        self.assertEqual(response["type"], 4)
        self.assertTrue(response["data"]["content"])
        self.assertNotIn("internal kaboom", response["data"]["content"])

    def test_command_returning_none_raises_runtime_error(self):
        fake_command = Mock(return_value=None)
        self._patch_command_map({"fake-command": {"function": fake_command, "params": []}})

        with self.assertRaises(RuntimeError) as ctx:
            bot.process_bot_command(_make_command_body("fake-command"), Mock())
        self.assertIn("did not return a message", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
