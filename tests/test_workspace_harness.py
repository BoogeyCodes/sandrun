from __future__ import annotations

import sys

import pytest

from sandrun.harness import run_in_sandbox
from sandrun.workspace import workspace

PY = sys.executable


def test_workspace_materialises_and_cleans_up():
    created = None
    with workspace({"a/b.txt": "hi", "top.txt": "yo"}) as root:
        created = root
        assert (root / "a" / "b.txt").read_text() == "hi"
        assert (root / "top.txt").read_text() == "yo"
    assert created is not None and not created.exists()


def test_overlay_overwrites_base_files():
    with workspace({"f.txt": "original"}, overlay={"f.txt": "changed"}) as root:
        assert (root / "f.txt").read_text() == "changed"


def test_workspace_rejects_path_traversal():
    with pytest.raises(ValueError), workspace({"../escape.txt": "nope"}):
        pass


def test_run_in_sandbox_runs_the_overlaid_code():
    files = {"calc.py": "def add(a, b):\n    return a - b\n"}  # buggy
    overlay = {"calc.py": "def add(a, b):\n    return a + b\n"}  # agent's fix
    test = {"test_calc.py": "from calc import add\nassert add(2, 3) == 5\nprint('ok')\n"}

    # Without the fix, the assertion fails.
    failing = run_in_sandbox({**files, **test}, [PY, "test_calc.py"])
    assert not failing.passed

    # With the agent's overlay, it passes.
    passing = run_in_sandbox({**files, **test}, [PY, "test_calc.py"], overlay=overlay)
    assert passing.passed
    assert "ok" in passing.stdout
