# MIRROR: src/aws_services.py — keep in sync (independent Lambda packaging prevents imports)
from dataclasses import dataclass


@dataclass
class AWSServices:
    """Bundle of pre-built AWS resource handles passed into deferred command
    handlers. Add a field per AWS resource the worker needs."""
