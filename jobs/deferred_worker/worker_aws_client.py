# MIRROR: src/aws_client.py — keep in sync (independent Lambda packaging prevents imports)

from worker_aws_services import AWSServices


_aws_services: AWSServices | None = None


def get_aws_services() -> AWSServices:
    """Return the lazily created AWSServices singleton."""
    global _aws_services
    if _aws_services is None:
        _aws_services = AWSServices(
        )
    return _aws_services
