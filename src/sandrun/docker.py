"""Build and run a `docker run` invocation for stronger sandbox isolation."""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from sandrun.result import RunResult


def build_docker_argv(
    image: str,
    command: Sequence[str],
    mount: str | Path,
    workdir: str = "/work",
    network: str | None = "none",
    env: Mapping[str, str] | None = None,
    memory: str | None = None,
) -> list[str]:
    """
    Construct the argv for `docker run`: an auto-removed container with the workspace bind-mounted,
    the working directory set, and networking disabled by default for safety.
    """
    argv = ["docker", "run", "--rm", "-w", workdir, "-v", f"{Path(mount).resolve()}:{workdir}"]
    if network is not None:
        argv += ["--network", network]
    if memory is not None:
        argv += ["--memory", memory]
    for key, value in (env or {}).items():
        argv += ["-e", f"{key}={value}"]
    argv.append(image)
    argv += list(command)
    return argv


def docker_available() -> bool:
    return shutil.which("docker") is not None


def run_docker(
    image: str,
    command: Sequence[str],
    mount: str | Path,
    timeout: float = 120.0,
    **kwargs: object,
) -> RunResult:
    """Run ``command`` inside ``image`` with ``mount`` bind-mounted. Requires Docker on the host."""
    argv = build_docker_argv(image, command, mount, **kwargs)  # type: ignore[arg-type]
    start = time.monotonic()
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        return RunResult(argv, None, time.monotonic() - start, True, _d(exc.stdout), _d(exc.stderr))
    return RunResult(argv, completed.returncode, time.monotonic() - start, False, completed.stdout, completed.stderr)


def _d(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return "" if value is None else str(value)
