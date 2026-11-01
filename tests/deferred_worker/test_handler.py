import importlib.util
import json
import os
import unittest
from unittest.mock import Mock, patch

import worker_messages

# Every job's entry point is handler.py, so it's loaded by path under a unique
# name rather than imported bare (see tests/job_imports.py).
_HANDLER_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "deferred_worker", "handler.py")
_spec = importlib.util.spec_from_file_location("deferred_worker_handler", _HANDLER_PATH)
worker_handler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker_handler)


def _sqs_event(command_name: str, text: str = "hello") -> dict:
    payload = {
        "command_name": command_name,
        "event_body": {
            "application_id": "999",
            "token": "interaction-token",
            "data": {"name": command_name, "options": [{"name": "text", "type": 3, "value": text}]},
        },
        "enqueued_at": 0,
    }
    return {"Records": [{"body": json.dumps(payload)}]}


class TestDeferredWorkerHandler(unittest.TestCase):
    def setUp(self):
        followup_patcher = patch.object(worker_handler.discord_followup, "send_followup")
        self.mock_followup = followup_patcher.start()
        self.addCleanup(followup_patcher.stop)

        services_patcher = patch.object(worker_handler.aws_client, "get_aws_services", return_value=Mock())
        services_patcher.start()
        self.addCleanup(services_patcher.stop)

    def test_known_command_posts_its_result_as_followup(self):
        fake = Mock(return_value={"content": "done hi there", "allowed_mentions": {"parse": []}})
        with patch.dict(worker_handler._COMMAND_HANDLERS, {"results-view": fake}):
            worker_handler.handler(_sqs_event("results-view", "hi there"), Mock())

        self.assertEqual(fake.call_args.args[0]["data"]["options"][0]["value"], "hi there")
        args, kwargs = self.mock_followup.call_args
        self.assertEqual(args[:2], ("999", "interaction-token"))
        self.assertIn("hi there", kwargs["content"])
        self.assertEqual(kwargs["allowed_mentions"], {"parse": []})

    def test_every_matchmaking_command_has_a_worker_handler(self):
        for name in ("request-matchmaking-role", "remove-matchmaking-role", "results-view", "get-fighter-role"):
            with self.subTest(command=name):
                self.assertIn(name, worker_handler._COMMAND_HANDLERS)

    def test_unknown_command_tells_the_user(self):
        worker_handler.handler(_sqs_event("not-registered"), Mock())

        content = self.mock_followup.call_args.args[2]
        self.assertIn("not-registered", content)

    def test_handler_exception_posts_general_error_instead_of_raising(self):
        # Raising would make SQS redeliver and re-run the command.
        with patch.dict(worker_handler._COMMAND_HANDLERS, {"results-view": Mock(side_effect=RuntimeError("boom"))}):
            worker_handler.handler(_sqs_event("results-view"), Mock())

        self.assertEqual(self.mock_followup.call_args.args[2], worker_messages.GENERAL_ERROR)


if __name__ == "__main__":
    unittest.main()
