"""Shared setup for the jobs/deferred_worker tests.

Worker modules read env vars at import time (via worker_constants), so assign
deterministic test values before any of them is imported; real host env vars
never leak through.

Jobs are packaged independently and import by bare name. Module names are kept
unique across jobs and against src/ so one job's tests cannot resolve another's
modules — tests/test_job_module_names.py fails if that is ever broken.
"""
import os
import sys

os.environ["REGION"] = "us-east-1"
os.environ["DISCORD_BOT_TOKEN_SECRET_NAME"] = "test-secret-name"
os.environ["DYNAMODB_TABLE_NAME"] = "test-table"

_WORKER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "deferred_worker"))
if _WORKER_DIR not in sys.path:
    sys.path.insert(0, _WORKER_DIR)
