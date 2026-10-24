"""The result of running a command in a sandbox."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunResult:
    command: list[str]
    exit_code: int | None  # None when the command timed out
    duration_s: float
    timed_out: bool
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        """A run passes only if it finished in time with a zero exit code."""
        return not self.timed_out and self.exit_code == 0

    def summary(self) -> str:
        if self.timed_out:
            return f"TIMED OUT after {self.duration_s:.1f}s"
        verdict = "PASS" if self.passed else "FAIL"
        return f"{verdict} (exit {self.exit_code}, {self.duration_s:.1f}s)"
