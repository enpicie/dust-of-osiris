"""Import support for the independently packaged Lambdas under jobs/.

Each job is zipped and deployed on its own, so its modules are imported by bare
name (`import db_helper`). At runtime that is unambiguous: one zip, one sys.path.

Under pytest every job shares a single interpreter and every job directory ends
up on sys.path, so two jobs defining the same module name would collide — and
`patch("some_module.attr")` re-resolves through sys.modules at call time, so the
collision surfaces as tests silently exercising the wrong job's code. Module
names are therefore kept unique across jobs (see test_job_module_names.py, which
fails if a new collision is introduced) rather than papered over here.

src/ is on the same sys.path (conftest.py), so a job module that shares a name
with a top-level src module collides the same way and is held to the same rule.
"""
import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_JOBS_ROOT = os.path.join(_REPO_ROOT, "jobs")
_SRC_ROOT = os.path.join(_REPO_ROOT, "src")

# Every job's Lambda entry point is handler.handler, so this name is expected to
# repeat. No test imports it by bare name.
SHARED_ENTRY_POINT_MODULE = "handler"


def module_names_by_job() -> dict:
    """Map each job directory name to the set of module names it defines."""
    names = {}
    for job_name in sorted(os.listdir(_JOBS_ROOT)):
        job_dir = os.path.join(_JOBS_ROOT, job_name)
        if not os.path.isdir(job_dir):
            continue
        names[job_name] = {
            f[:-3] for f in os.listdir(job_dir)
            if f.endswith(".py") and f[:-3] != SHARED_ENTRY_POINT_MODULE
        }
    return names


def src_top_level_module_names() -> set:
    """Names importable bare from src/: its top-level modules and packages."""
    names = set()
    for entry in os.listdir(_SRC_ROOT):
        path = os.path.join(_SRC_ROOT, entry)
        if entry.endswith(".py"):
            names.add(entry[:-3])
        elif os.path.isdir(path) and os.path.isfile(os.path.join(path, "__init__.py")):
            names.add(entry)
    return names
