"""Guards on the merged command map — the same dict scripts/register_commands.py
sends to Discord, so these catch registration failures before a deploy does."""
import re
import unittest

import commands.command_map as command_map

# https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-naming
_COMMAND_NAME_PATTERN = re.compile(r"^[-_\w]{1,32}$")
_DISCORD_DESCRIPTION_MAX = 100


class TestCommandMap(unittest.TestCase):
    def test_every_name_is_a_valid_lowercase_discord_command_name(self):
        for name in command_map.command_map:
            with self.subTest(command=name):
                self.assertRegex(name, _COMMAND_NAME_PATTERN)
                self.assertEqual(name, name.lower())

    def test_every_entry_has_a_callable_and_a_description_within_discords_limit(self):
        for name, entry in command_map.command_map.items():
            with self.subTest(command=name):
                self.assertTrue(callable(entry["function"]))
                self.assertTrue(entry["description"])
                self.assertLessEqual(len(entry["description"]), _DISCORD_DESCRIPTION_MAX)

    def test_every_param_description_is_within_discords_limit(self):
        for name, entry in command_map.command_map.items():
            for param in entry["params"]:
                with self.subTest(command=name, param=param.name):
                    self.assertLessEqual(len(param.description), _DISCORD_DESCRIPTION_MAX)

    def test_autocomplete_params_have_a_handler(self):
        # bot.process_input_autocomplete raises at runtime if a param is flagged
        # autocomplete but has no handler; catch it here instead.
        for name, entry in command_map.command_map.items():
            for param in entry["params"]:
                if param.autocomplete:
                    with self.subTest(command=name, param=param.name):
                        self.assertIsNotNone(param.autocomplete_handler)

    def test_required_params_come_before_optional_ones(self):
        # Discord rejects registration otherwise.
        for name, entry in command_map.command_map.items():
            required_flags = [p.required for p in entry["params"]]
            with self.subTest(command=name):
                self.assertEqual(required_flags, sorted(required_flags, reverse=True))


if __name__ == "__main__":
    unittest.main()
