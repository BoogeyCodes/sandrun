from __future__ import annotations

import sys
from pathlib import Path

import pytest

from sandrun.runner import run_local

PY = sys.executable


def test_successful_command_passes(tmp_path: Path):
    result = run_local([PY, "-c", "print('hello')"], cwd=tmp_path)
    assert result.passed
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert not result.timed_out


def test_failing_command_does_not_pass(tmp_path: Path):
    result = run_local([PY, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"], cwd=tmp_path)
    assert not result.passed
    assert result.exit_code == 3
    assert "boom" in result.stderr
    assert "boom" in result.combined_output
    assert result.tail() == "boom"


def test_tail_keeps_only_the_last_lines(tmp_path: Path):
    result = run_local([PY, "-c", "print('\\n'.join(str(i) for i in range(50)))"], cwd=tmp_path)
    tail = result.tail(3)
    assert tail.splitlines() == ["47", "48", "49"]
    assert result.tail(0) == ""


def test_timeout_is_reported(tmp_path: Path):
    result = run_local([PY, "-c", "import time; time.sleep(5)"], cwd=tmp_path, timeout=0.5)
    assert result.timed_out
    assert not result.passed
    assert result.exit_code is None
    assert "TIMED OUT" in result.summary()


def test_runs_in_the_given_directory(tmp_path: Path):
    (tmp_path / "marker.txt").write_text("x")
    result = run_local([PY, "-c", "import os; print(os.path.exists('marker.txt'))"], cwd=tmp_path)
    assert "True" in result.stdout


def test_empty_command_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        run_local([], cwd=tmp_path)
