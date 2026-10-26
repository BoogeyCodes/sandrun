"""Tie it together: materialise a task, apply the agent's changes, and run its tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sandrun.result import RunResult
from sandrun.runner import run_local
from sandrun.workspace import workspace


def run_in_sandbox(
    files: Mapping[str, str],
    command: Sequence[str],
    overlay: Mapping[str, str] | None = None,
    timeout: float = 120.0,
    env: Mapping[str, str] | None = None,
) -> RunResult:
    """
    Write ``files`` (the starting repo) and then ``overlay`` (the agent's changed files) into a fresh
    workspace, run ``command`` there, and return the result. The workspace is deleted afterwards.
    """
    with workspace(files, overlay) as root:
        return run_local(command, cwd=root, timeout=timeout, env=env)
