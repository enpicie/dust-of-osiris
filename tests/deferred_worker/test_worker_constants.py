import os
import re
import unittest

import commands.matchmaking.matchmaking_commands as src_matchmaking_commands
import worker_constants as constants
from matchmaking_rules import Tier

_ROLES_TF = os.path.join(os.path.dirname(__file__), "..", "..", "terraform", "infra", "matchmaking_roles.tf")


def _role_ids_by_env() -> dict[str, dict[str, str]]:
    """The tier -> role ID maps written in terraform/infra/matchmaking_roles.tf."""
    with open(_ROLES_TF, encoding="utf-8") as f:
        source = f.read()
    return {
        env: dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', body))
        for env, body in re.findall(r"\b(dev|prod) = \{([^{}]*)\}", source)
    }


class TestParseRoleIds(unittest.TestCase):
    def test_parses_the_json_terraform_passes_in(self):
        raw = '{"novice": "1", "fighter": "2", "ascended": "3", "elite": "4"}'
        self.assertEqual(constants.parse_role_ids(raw), {"novice": "1", "fighter": "2", "ascended": "3", "elite": "4"})

    def test_missing_or_unreadable_means_not_configured(self):
        for raw in (None, "", "not json", "[1, 2]"):
            with self.subTest(raw=raw):
                self.assertEqual(constants.parse_role_ids(raw), {})


class TestTerraformRoleIds(unittest.TestCase):
    """matchmaking_roles.tf is the single source of role IDs; its keys must be
    exactly the bot's tier names or the worker treats roles as unconfigured."""

    def test_every_environment_defines_exactly_the_bot_tiers(self):
        by_env = _role_ids_by_env()
        self.assertEqual(set(by_env), {"dev", "prod"})
        for env, role_ids in by_env.items():
            with self.subTest(env=env):
                self.assertEqual(set(role_ids), {tier.name.lower() for tier in Tier})

    def test_every_role_id_is_a_discord_id_and_unique_within_its_environment(self):
        for env, role_ids in _role_ids_by_env().items():
            with self.subTest(env=env):
                for role_id in role_ids.values():
                    self.assertRegex(role_id, r"^\d{17,20}$")
                self.assertEqual(len(set(role_ids.values())), len(role_ids))


class TestRoleChoicesMatchTiers(unittest.TestCase):
    def test_remove_command_choices_are_exactly_the_worker_tiers(self):
        # MIRROR: src/commands/matchmaking/matchmaking_commands.py ROLE_CHOICES is sent to
        # the worker, which looks the value up as a Tier name.
        self.assertEqual(set(src_matchmaking_commands.ROLE_CHOICES), {tier.name.lower() for tier in Tier})
        for value, label in src_matchmaking_commands.ROLE_CHOICES.items():
            self.assertEqual(label, Tier[value.upper()].label)


if __name__ == "__main__":
    unittest.main()
