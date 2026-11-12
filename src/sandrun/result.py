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

    @property
    def combined_output(self) -> str:
        """stdout and stderr together, in the order a terminal would show them."""
        return self.stdout + self.stderr

    def head(self, lines: int = 20) -> str:
        """The first ``lines`` lines of combined output — useful when the failure is at startup."""
        if lines <= 0:
            return ""
        return "\n".join(self.combined_output.splitlines()[:lines])

    def tail(self, lines: int = 20) -> str:
        """The last ``lines`` lines of combined output — enough to see why a run failed
        without dumping the whole log into a report."""
        if lines <= 0:
            return ""
        return "\n".join(self.combined_output.splitlines()[-lines:])

    def summary(self) -> str:
        if self.timed_out:
            return f"TIMED OUT after {self.duration_s:.1f}s"
        verdict = "PASS" if self.passed else "FAIL"
        return f"{verdict} (exit {self.exit_code}, {self.duration_s:.1f}s)"
