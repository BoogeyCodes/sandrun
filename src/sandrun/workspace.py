"""Create a throwaway workspace from a set of files."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path


def _write_files(root: Path, files: Mapping[str, str]) -> None:
    for relative, content in files.items():
        target = root / relative
        if not _is_within(root, target):
            raise ValueError(f"refusing to write outside the workspace: {relative!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _is_within(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


@contextmanager
def workspace(files: Mapping[str, str] | None = None, overlay: Mapping[str, str] | None = None) -> Iterator[Path]:
    """
    Create a temporary directory, write ``files`` into it, then write ``overlay`` on top (the agent's
    changes), and yield its path. The directory is removed on exit. Paths that would escape the
    workspace (e.g. ``../x``) are rejected.
    """
    root = Path(tempfile.mkdtemp(prefix="sandrun-"))
    try:
        if files:
            _write_files(root, files)
        if overlay:
            _write_files(root, overlay)
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
