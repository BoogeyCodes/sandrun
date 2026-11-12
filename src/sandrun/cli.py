"""Command-line entry point: run a command in a fresh copy of a directory, isolated and timed."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from sandrun import __version__
from sandrun.runner import run_local


def _serve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="sandrun serve", description="Run the web dashboard + REST API.")
    parser.add_argument("--db", default="sandrun.db", help="SQLite file to store runs in")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="port to listen on (default: 8000)")
    args = parser.parse_args(argv)
    try:
        import uvicorn

        from sandrun.service import create_app
    except ImportError:
        print(
            "sandrun: the web server needs the optional extra. Install it with:\n"
            "    pip install 'sandrun[web]'",
            file=sys.stderr,
        )
        return 2
    uvicorn.run(create_app(args.db), host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    args_in = sys.argv[1:] if argv is None else argv
    if args_in and args_in[0] == "serve":
        return _serve(args_in[1:])

    parser = argparse.ArgumentParser(
        prog="sandrun",
        description="Run a command in a throwaway copy of a directory, with a timeout. "
        "Use 'sandrun serve' for the web dashboard + REST API.",
    )
    parser.add_argument("--dir", default=".", help="the directory to copy into the sandbox (default: .)")
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds before the command is killed")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="the command to run (after --)")
    args = parser.parse_args(argv)

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("sandrun: no command given (use: sandrun [options] -- <command>)", file=sys.stderr)
        return 2

    source = Path(args.dir)
    if not source.is_dir():
        print(f"sandrun: {args.dir}: not a directory", file=sys.stderr)
        return 2

    sandbox = Path(tempfile.mkdtemp(prefix="sandrun-"))
    try:
        shutil.copytree(source, sandbox, dirs_exist_ok=True)
        result = run_local(command, cwd=sandbox, timeout=args.timeout)
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    print(f"\n[sandrun] {result.summary()}", file=sys.stderr)
    return 0 if result.passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
