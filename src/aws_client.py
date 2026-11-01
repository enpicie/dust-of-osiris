# MIRROR: jobs/deferred_worker/worker_aws_client.py — keep in sync (independent Lambda packaging prevents imports)
import boto3

import constants
from aws_services import AWSServices

_sqs = boto3.resource("sqs", region_name=constants.AWS_REGION)

_aws_services: AWSServices | None = None


def get_aws_services() -> AWSServices:
    """Return the shared AWSServices instance, building it on first call
    and memoizing it for the lifetime of the Lambda container."""
    global _aws_services
    if _aws_services is None:
        _aws_services = AWSServices(
            deferred_worker_sqs_queue=_sqs.Queue(constants.SQS_DEFERRED_WORKER_QUEUE_URL),
        )
    return _aws_services
