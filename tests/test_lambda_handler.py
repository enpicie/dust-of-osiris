import json
import os
import unittest
from unittest.mock import Mock, patch

# aws_client (imported by lambda_handler) creates boto3 resources at import time;
# make sure a region resolves deterministically regardless of host AWS config.
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import constants
import lambda_handler
from utils.discord_auth_helper import SignatureVerificationError


def _make_event(body_dict: dict) -> dict:
    return {
        "body": json.dumps(body_dict),
        "headers": {
            "x-signature-ed25519": "ab" * 64,
            "x-signature-timestamp": "1700000000",
        },
    }


class TestLambdaHandlerRouting(unittest.TestCase):
    def setUp(self):
        # Auth passes by default; individual tests override the side effect.
        verify_patcher = patch.object(lambda_handler.auth_helper, "verify_signature", return_value=None)
        self.mock_verify = verify_patcher.start()
        self.addCleanup(verify_patcher.stop)

        services_patcher = patch.object(lambda_handler.aws_client, "get_aws_services")
        self.mock_get_services = services_patcher.start()
        self.mock_services = Mock()
        self.mock_get_services.return_value = self.mock_services
        self.addCleanup(services_patcher.stop)

    def test_ping_body_returns_ping_pong_response(self):
        response = lambda_handler.lambda_handler(_make_event({"type": 1}), Mock())
        self.assertEqual(response, constants.PING_PONG_RESPONSE)

    def test_application_command_routes_to_process_bot_command(self):
        body = {"type": 2, "data": {"name": "ping"}}
        command_response = {"type": 4, "data": {"content": "command handled"}}
        with patch.object(lambda_handler.bot, "process_bot_command", return_value=command_response) as mock_process:
            response = lambda_handler.lambda_handler(_make_event(body), Mock())
        mock_process.assert_called_once_with(body, self.mock_services)
        self.assertEqual(response, command_response)

    def test_autocomplete_routes_to_process_input_autocomplete(self):
        body = {"type": 4, "data": {"name": "note"}}
        autocomplete_response = {"type": 8, "data": {"choices": []}}
        with patch.object(lambda_handler.bot, "process_input_autocomplete", return_value=autocomplete_response) as mock_autocomplete:
            response = lambda_handler.lambda_handler(_make_event(body), Mock())
        mock_autocomplete.assert_called_once_with(body, self.mock_services)
        self.assertEqual(response, autocomplete_response)

    def test_signature_failure_raises_unauthorized(self):
        self.mock_verify.side_effect = SignatureVerificationError("Verification failed")
        with self.assertRaises(Exception) as ctx:
            lambda_handler.lambda_handler(_make_event({"type": 1}), Mock())
        self.assertIn("[UNAUTHORIZED]", str(ctx.exception))

    def test_unexpected_auth_error_also_raises_unauthorized(self):
        # e.g. a malformed (non-hex) signature header causes TypeError/ValueError inside
        # verify_signature; missing headers now raise SignatureVerificationError directly.
        self.mock_verify.side_effect = TypeError("fromhex arg must be str")
        with self.assertRaises(Exception) as ctx:
            lambda_handler.lambda_handler(_make_event({"type": 1}), Mock())
        self.assertIn("[UNAUTHORIZED]", str(ctx.exception))

    def test_unsupported_interaction_type_returns_general_error_response(self):
        # MODAL_SUBMIT (5) is not routed; the handler swallows the error and
        # returns the generic error ResponseMessage dict.
        response = lambda_handler.lambda_handler(_make_event({"type": 5}), Mock())
        self.assertEqual(response["type"], 4)
        self.assertTrue(response["data"]["content"])

    def test_command_exception_returns_general_error_response(self):
        body = {"type": 2, "data": {"name": "boom"}}
        with patch.object(lambda_handler.bot, "process_bot_command", side_effect=RuntimeError("kaboom")):
            response = lambda_handler.lambda_handler(_make_event(body), Mock())
        self.assertEqual(response["type"], 4)
        self.assertTrue(response["data"]["content"])

    def test_empty_body_returns_not_lambda_event_message(self):
        event = {"body": "", "headers": {}}
        response = lambda_handler.lambda_handler(event, Mock())
        self.assertEqual(response, {"message": "Request is not Lambda event: 'body-json' not found"})


if __name__ == "__main__":
    unittest.main()
