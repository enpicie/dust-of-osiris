import unittest
from unittest.mock import Mock, patch

import utils.discord_api_helper as discord_api_helper


class TestBotToken(unittest.TestCase):
    def setUp(self):
        # Reset the module-level cache between tests.
        patcher_token = patch.object(discord_api_helper, "_bot_token", None)
        patcher_client = patch.object(discord_api_helper, "_secretsmanager_client", None)
        patcher_token.start()
        patcher_client.start()
        self.addCleanup(patcher_token.stop)
        self.addCleanup(patcher_client.stop)

    def test_token_is_fetched_once_from_secrets_manager_and_cached(self):
        client = Mock()
        client.get_secret_value.return_value = {"SecretString": "test-token-value"}
        with patch.object(discord_api_helper.boto3, "client", return_value=client), \
             patch.object(discord_api_helper.constants, "DISCORD_BOT_TOKEN_SECRET_NAME", "my-secret"):
            first = discord_api_helper._get_bot_token()
            second = discord_api_helper._get_bot_token()

        self.assertEqual(first, "test-token-value")
        self.assertEqual(second, "test-token-value")
        client.get_secret_value.assert_called_once_with(SecretId="my-secret")


class TestGetGuildName(unittest.TestCase):
    def test_returns_name_on_200(self):
        response = Mock(status_code=200)
        response.json.return_value = {"name": "My Server"}
        with patch.object(discord_api_helper, "_request", return_value=response):
            self.assertEqual(discord_api_helper.get_guild_name("123"), "My Server")

    def test_returns_none_on_error(self):
        response = Mock(status_code=403)
        response.json.return_value = {"message": "Missing Access"}
        with patch.object(discord_api_helper, "_request", return_value=response):
            self.assertIsNone(discord_api_helper.get_guild_name("123"))


if __name__ == "__main__":
    unittest.main()
