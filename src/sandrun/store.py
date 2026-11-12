"""Persist sandbox runs and summarise pass/fail across them.

Dependency-free (standard-library ``sqlite3``), so it stays part of sandrun's core. The web service
builds on it, but you can use it on its own to keep a history of runs and track a pass rate over time.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sandrun.result import RunResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    label      TEXT NOT NULL,
    command    TEXT NOT NULL,
    status     TEXT NOT NULL,
    exit_code  INTEGER,
    duration_s REAL NOT NULL,
    timed_out  INTEGER NOT NULL,
    stdout     TEXT NOT NULL,
    stderr     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
"""


def status_of(result: RunResult) -> str:
    """Map a RunResult onto a short status word: passed / failed / timeout."""
    if result.timed_out:
        return "timeout"
    return "passed" if result.exit_code == 0 else "failed"


@dataclass(frozen=True)
class StoredRun:
    """A run read back from the store."""

    id: int
    created_at: str
    label: str
    command: list[str]
    status: str
    exit_code: int | None
    duration_s: float
    timed_out: bool
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def combined_output(self) -> str:
        return self.stdout + self.stderr

    def result(self) -> RunResult:
        """Rebuild the original :class:`RunResult` (without the id/label/status wrapper)."""
        return RunResult(
            command=self.command,
            exit_code=self.exit_code,
            duration_s=self.duration_s,
            timed_out=self.timed_out,
            stdout=self.stdout,
            stderr=self.stderr,
        )


@dataclass(frozen=True)
class RunSummary:
    id: int
    created_at: str
    label: str
    command: list[str]
    status: str
    exit_code: int | None
    duration_s: float


@dataclass(frozen=True)
class Stats:
    total: int
    passed: int
    failed: int
    timeout: int
    error: int
    avg_duration_s: float

    @property
    def pass_rate(self) -> float:
        """Share of runs that passed (0-1)."""
        return round(self.passed / self.total, 3) if self.total else 0.0


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class RunStore:
    """A SQLite-backed history of sandbox runs. Use as a context manager, or call :meth:`close`."""

    def __init__(self, path: str | Path = "sandrun.db") -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def __enter__(self) -> RunStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    # -- writes ----------------------------------------------------------
    def add(self, result: RunResult, label: str = "", status: str | None = None) -> StoredRun:
        """Store a finished run. ``status`` defaults to one derived from the result."""
        created_at = _now()
        st = status or status_of(result)
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO runs (created_at, label, command, status, exit_code, duration_s, timed_out, "
                "stdout, stderr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at,
                    label,
                    json.dumps(result.command),
                    st,
                    result.exit_code,
                    result.duration_s,
                    int(result.timed_out),
                    result.stdout,
                    result.stderr,
                ),
            )
            run_id = int(cur.lastrowid)
            self._conn.commit()
        return StoredRun(
            id=run_id,
            created_at=created_at,
            label=label,
            command=list(result.command),
            status=st,
            exit_code=result.exit_code,
            duration_s=result.duration_s,
            timed_out=result.timed_out,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def delete(self, run_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # -- reads -----------------------------------------------------------
    def get(self, run_id: int) -> StoredRun | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return self._to_run(row)

    def list(self, limit: int = 100, offset: int = 0, status: str | None = None) -> list[RunSummary]:
        query = "SELECT id, created_at, label, command, status, exit_code, duration_s FROM runs"
        params: list[object] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [
            RunSummary(
                id=r["id"],
                created_at=r["created_at"],
                label=r["label"],
                command=json.loads(r["command"]),
                status=r["status"],
                exit_code=r["exit_code"],
                duration_s=r["duration_s"],
            )
            for r in rows
        ]

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])

    def stats(self) -> Stats:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(status = 'passed')  AS passed,
                       SUM(status = 'failed')  AS failed,
                       SUM(status = 'timeout') AS timeout,
                       SUM(status = 'error')   AS error,
                       AVG(duration_s)         AS avg_duration
                FROM runs
                """
            ).fetchone()
        total = row["total"] or 0
        return Stats(
            total=total,
            passed=row["passed"] or 0,
            failed=row["failed"] or 0,
            timeout=row["timeout"] or 0,
            error=row["error"] or 0,
            avg_duration_s=round(row["avg_duration"] or 0.0, 3),
        )

    def _to_run(self, row: sqlite3.Row) -> StoredRun:
        return StoredRun(
            id=row["id"],
            created_at=row["created_at"],
            label=row["label"],
            command=json.loads(row["command"]),
            status=row["status"],
            exit_code=row["exit_code"],
            duration_s=row["duration_s"],
            timed_out=bool(row["timed_out"]),
            stdout=row["stdout"],
            stderr=row["stderr"],
        )
