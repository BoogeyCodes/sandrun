"""sandrun: run an AI coding agent's work against tests in an isolated sandbox.

Materialise a task's files (plus the agent's changes) into a throwaway workspace, run a test command
with a timeout, and return a structured pass/fail result — locally, or inside a Docker container for
stronger isolation. Dependency-free.
"""

from sandrun.docker import build_docker_argv
from sandrun.harness import run_in_sandbox
from sandrun.result import RunResult
from sandrun.runner import run_local
from sandrun.store import RunStore, RunSummary, Stats, StoredRun, status_of
from sandrun.workspace import workspace

__version__ = "0.2.0"
__all__ = [
    "RunResult",
    "run_local",
    "workspace",
    "run_in_sandbox",
    "build_docker_argv",
    "RunStore",
    "StoredRun",
    "RunSummary",
    "Stats",
    "status_of",
]
