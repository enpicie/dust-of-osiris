import unittest
from collections import defaultdict

from tests import job_imports


class TestJobModuleNamesAreUnique(unittest.TestCase):
    """Jobs are packaged independently and import by bare name, so at runtime a
    repeated module name is harmless. In the test suite every job directory is on
    one sys.path, and `patch("module.attr")` re-resolves through sys.modules at
    call time — so a shared name makes one job's tests exercise another job's
    code, quietly. Keep the names unique instead."""

    def test_no_module_name_is_defined_by_two_jobs(self):
        owners = defaultdict(list)
        for job_name, module_names in job_imports.module_names_by_job().items():
            for module_name in module_names:
                owners[module_name].append(job_name)

        collisions = {name: jobs for name, jobs in owners.items() if len(jobs) > 1}
        self.assertEqual(
            collisions, {},
            f"Module names shared across jobs: {collisions}. "
            "Rename one side (e.g. the worker_ prefix in jobs/deferred_worker).",
        )

    def test_no_job_module_shares_a_name_with_a_top_level_src_module(self):
        # src/ is on the test sys.path too, so `import constants` from a job's
        # module can resolve to src/constants.py (or the reverse) depending on
        # which test ran first.
        src_names = job_imports.src_top_level_module_names()
        collisions = {
            job_name: sorted(module_names & src_names)
            for job_name, module_names in job_imports.module_names_by_job().items()
            if module_names & src_names
        }
        self.assertEqual(
            collisions, {},
            f"Job modules shadowing top-level src modules: {collisions}. "
            "Rename the job's copy (e.g. worker_constants in jobs/deferred_worker).",
        )

    def test_src_top_level_names_are_discovered(self):
        # Guards the rule above against passing vacuously on an empty scan.
        self.assertTrue({"constants", "aws_client", "aws_services", "commands"} <= job_imports.src_top_level_module_names())


if __name__ == "__main__":
    unittest.main()
