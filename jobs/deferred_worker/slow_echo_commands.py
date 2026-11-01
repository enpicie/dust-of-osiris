import logging

from worker_aws_services import AWSServices

logger = logging.getLogger()


def handle_slow_echo(event_body: dict, aws_services: AWSServices) -> str:
    """Worker half of /slow-echo. Real handlers do the slow work here — external
    API calls, bulk DynamoDB writes, file generation — then return the followup.

    Return a str for plain content, or a dict of send_followup kwargs
    ({"content": ..., "allowed_mentions": ..., "flags": ...}).
    """
    options = event_body.get("data", {}).get("options", [])
    text = next((o["value"] for o in options if o["name"] == "text"), "")
    logger.info(f"[slow_echo] echoing length={len(text)}")
    return {
        "content": f"🔁 {text}",
        "allowed_mentions": {"parse": []},  # never let echoed text ping anyone
    }
