from __future__ import annotations

from sandrun.result import RunResult
from sandrun.store import RunStore, status_of


def _result(exit_code=0, timed_out=False, stdout="out", stderr="", command=None, duration=0.1):
    return RunResult(
        command=command or ["echo", "hi"],
        exit_code=exit_code,
        duration_s=duration,
        timed_out=timed_out,
        stdout=stdout,
        stderr=stderr,
    )


def test_status_of():
    assert status_of(_result(exit_code=0)) == "passed"
    assert status_of(_result(exit_code=1)) == "failed"
    assert status_of(_result(exit_code=None, timed_out=True)) == "timeout"


def test_add_get_roundtrip():
    with RunStore(":memory:") as store:
        stored = store.add(_result(stdout="hello\n", command=["pytest"]), label="suite")
        assert stored.id == 1
        assert stored.status == "passed"
        got = store.get(stored.id)
        assert got is not None
        assert got.label == "suite"
        assert got.command == ["pytest"]
        assert got.stdout == "hello\n"
        assert got.passed
        # rebuildable into the original RunResult
        assert got.result().passed


def test_list_filters_by_status():
    with RunStore(":memory:") as store:
        store.add(_result(exit_code=0))
        store.add(_result(exit_code=1))
        store.add(_result(exit_code=None, timed_out=True))
        assert store.count() == 3
        assert [r.id for r in store.list()] == [3, 2, 1]  # newest first
        assert len(store.list(status="passed")) == 1
        assert store.list(status="failed")[0].status == "failed"


def test_delete():
    with RunStore(":memory:") as store:
        stored = store.add(_result())
        assert store.delete(stored.id) is True
        assert store.get(stored.id) is None
        assert store.delete(stored.id) is False


def test_stats_and_pass_rate():
    with RunStore(":memory:") as store:
        store.add(_result(exit_code=0, duration=1.0))
        store.add(_result(exit_code=0, duration=3.0))
        store.add(_result(exit_code=2, duration=2.0))
        store.add(_result(exit_code=None, timed_out=True, duration=0.0))

        s = store.stats()
        assert s.total == 4
        assert s.passed == 2
        assert s.failed == 1
        assert s.timeout == 1
        assert s.pass_rate == 0.5
        assert s.avg_duration_s == 1.5


def test_stats_empty_store():
    with RunStore(":memory:") as store:
        s = store.stats()
        assert s.total == 0
        assert s.pass_rate == 0.0
