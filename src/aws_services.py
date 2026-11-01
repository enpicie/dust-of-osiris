# MIRROR: jobs/deferred_worker/worker_aws_services.py — keep in sync (independent Lambda packaging prevents imports)
from dataclasses import dataclass

from mypy_boto3_sqs.service_resource import Queue

@dataclass
class AWSServices:
    """Container bundling the AWS resource clients the bot needs, so handlers
    receive one injectable dependency. Add a field per AWS resource."""
    deferred_worker_sqs_queue: Queue
