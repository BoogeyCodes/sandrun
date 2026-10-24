"""Run a command locally and capture the result."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from sandrun.result import RunResult


def run_local(
    command: Sequence[str],
    cwd: str | Path,
    timeout: float = 120.0,
    env: Mapping[str, str] | None = None,
) -> RunResult:
    """
    Run ``command`` in ``cwd`` with a timeout, capturing stdout and stderr. A command that exceeds the
    timeout is killed and reported as ``timed_out``.
    """
    argv = list(command)
    if not argv:
        raise ValueError("command must not be empty")

    start = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            env=dict(env) if env is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            command=argv,
            exit_code=None,
            duration_s=time.monotonic() - start,
            timed_out=True,
            stdout=_decode(exc.stdout),
            stderr=_decode(exc.stderr),
        )

    return RunResult(
        command=argv,
        exit_code=completed.returncode,
        duration_s=time.monotonic() - start,
        timed_out=False,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _decode(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)
