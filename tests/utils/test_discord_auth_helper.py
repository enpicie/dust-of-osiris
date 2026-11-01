import unittest
from unittest.mock import patch

from nacl.signing import SigningKey

import utils.discord_auth_helper as discord_auth_helper
from utils.discord_auth_helper import SignatureVerificationError


def _make_signed_event(signing_key: SigningKey, body: str, timestamp: str = "1700000000") -> dict:
    """Builds an API-Gateway-style event signed the way Discord signs requests:
    ed25519 over f"{timestamp}{body}", hex-encoded in the x-signature-ed25519 header."""
    signature = signing_key.sign(f"{timestamp}{body}".encode()).signature.hex()
    return {
        "body": body,
        "headers": {
            "x-signature-ed25519": signature,
            "x-signature-timestamp": timestamp,
        },
    }


class TestIsPingPong(unittest.TestCase):
    def test_type_1_is_ping_pong(self):
        self.assertTrue(discord_auth_helper.is_ping_pong({"type": 1}))

    def test_type_2_is_not_ping_pong(self):
        self.assertFalse(discord_auth_helper.is_ping_pong({"type": 2}))

    def test_missing_type_key_is_not_ping_pong(self):
        self.assertFalse(discord_auth_helper.is_ping_pong({}))

    def test_none_type_is_not_ping_pong(self):
        self.assertFalse(discord_auth_helper.is_ping_pong({"type": None}))


class TestVerifySignature(unittest.TestCase):
    def setUp(self):
        self.signing_key = SigningKey.generate()
        public_key_hex = self.signing_key.verify_key.encode().hex()
        patcher = patch.object(discord_auth_helper.constants, "BOT_PUBLIC_KEY", public_key_hex)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_correctly_signed_request_passes(self):
        event = _make_signed_event(self.signing_key, '{"type": 1}')
        # Must not raise.
        discord_auth_helper.verify_signature(event)

    def test_tampered_body_raises_signature_verification_error(self):
        event = _make_signed_event(self.signing_key, '{"type": 1}')
        event["body"] = '{"type": 2}'
        with self.assertRaises(SignatureVerificationError):
            discord_auth_helper.verify_signature(event)

    def test_tampered_timestamp_raises_signature_verification_error(self):
        event = _make_signed_event(self.signing_key, '{"type": 1}', timestamp="1700000000")
        event["headers"]["x-signature-timestamp"] = "1700000001"
        with self.assertRaises(SignatureVerificationError):
            discord_auth_helper.verify_signature(event)

    def test_signature_from_wrong_key_raises_signature_verification_error(self):
        attacker_key = SigningKey.generate()
        event = _make_signed_event(attacker_key, '{"type": 1}')
        with self.assertRaises(SignatureVerificationError):
            discord_auth_helper.verify_signature(event)

    def test_missing_signature_header_raises_signature_verification_error(self):
        event = _make_signed_event(self.signing_key, '{"type": 1}')
        del event["headers"]["x-signature-ed25519"]
        with self.assertRaises(SignatureVerificationError):
            discord_auth_helper.verify_signature(event)

    def test_missing_timestamp_header_raises_signature_verification_error(self):
        event = _make_signed_event(self.signing_key, '{"type": 1}')
        del event["headers"]["x-signature-timestamp"]
        with self.assertRaises(SignatureVerificationError):
            discord_auth_helper.verify_signature(event)


if __name__ == "__main__":
    unittest.main()
