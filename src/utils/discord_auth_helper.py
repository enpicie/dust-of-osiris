from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import constants
from enums import DiscordInteractionType


class SignatureVerificationError(Exception):
    """Raised when a request fails Discord signature verification."""
    pass


# Discord uses "ping pong" message to verify bot.
def is_ping_pong(body: dict) -> bool:
    return body.get("type") == DiscordInteractionType.PING

# Discord needs to verify bot application.
def verify_signature(event: dict):
    event_body = event["body"]
    verify_key = VerifyKey(bytes.fromhex(constants.BOT_PUBLIC_KEY))
    # Expected headers from Discord verification request.
    auth_signature = event["headers"].get("x-signature-ed25519")
    auth_timestamp = event["headers"].get("x-signature-timestamp")

    if auth_signature is None or auth_timestamp is None:
        raise SignatureVerificationError("Missing signature headers")

    try:
        verify_key.verify(f"{auth_timestamp}{event_body}".encode(), bytes.fromhex(auth_signature))
    except BadSignatureError as e:
        raise SignatureVerificationError("Verification failed") from e
