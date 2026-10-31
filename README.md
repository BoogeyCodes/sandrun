# sandrun

[![CI](https://github.com/BoogeyCodes/sandrun/actions/workflows/ci.yml/badge.svg)](https://github.com/BoogeyCodes/sandrun/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)
![No dependencies](https://img.shields.io/badge/dependencies-none-success)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

Run an **AI coding agent's work against tests in an isolated sandbox**. Materialise the task's files
plus the agent's changes into a throwaway workspace, run a test command with a timeout, and get a
structured pass/fail result — locally, or inside a Docker container for stronger isolation. No
dependencies.

```python
from sandrun import run_in_sandbox

result = run_in_sandbox(
    files={"calc.py": "def add(a, b):\n    return a - b\n",            # buggy repo
           "test_calc.py": "from calc import add\nassert add(2, 3) == 5\n"},
    overlay={"calc.py": "def add(a, b):\n    return a + b\n"},         # the agent's fix
    command=["python", "test_calc.py"],
)
result.passed        # True — the agent's change makes the test pass
result.summary()     # "PASS (exit 0, 0.1s)"
```

```bash
sandrun --dir ./repo -- pytest -q          # run tests in a throwaway copy of ./repo
sandrun --timeout 30 -- npm test           # with a timeout; exit 0 on pass, 1 on fail
```

## Why

Deciding whether an AI coding agent actually fixed the bug means *running its code against the tests* —
objectively, not by eye. But you want to do that without letting an unknown change touch your working
tree or your machine. sandrun is that harness: it copies the task into a disposable workspace, applies
the agent's changed files on top, runs the tests under a timeout, and reports a clean pass/fail, so an
evaluation can be backed by a real test result. It leans on the exact skills the work needs — shell,
subprocess, Docker, and test pipelines.

## What it does

- **`run_in_sandbox(files, command, overlay=None, timeout=...)`** — write the starting `files`, then
  the agent's `overlay` files on top, into a fresh temp directory; run `command` there; delete the
  workspace afterwards. Returns a `RunResult`.
- **`run_local(command, cwd, timeout)`** — run a command with captured output and a timeout; a command
  that overruns is killed and reported as `timed_out`.
- **`workspace(files, overlay=None)`** — a context manager that builds and cleans up a temp workspace,
  rejecting any path that would escape it (`../x`).
- **Docker**: `build_docker_argv(image, command, mount, network="none", memory=..., env=...)` builds a
  `docker run --rm` invocation with the workspace bind-mounted, the working dir set, and networking
  **off by default**; `run_docker(...)` executes it when Docker is present.

`RunResult` is `{ command, exit_code, duration_s, timed_out, stdout, stderr }` with a `passed` property
(finished in time with exit code 0) and a `summary()`.

## CLI

```
sandrun [--dir DIR] [--timeout SECONDS] -- <command>
```

Copies `DIR` (default `.`) into a throwaway sandbox, runs the command there, streams its output, prints
a `PASS`/`FAIL`/`TIMED OUT` line, and exits `0` on pass, `1` on fail, `2` on a usage error.

## Safety

The workspace is a temp directory removed on exit; path traversal in the file set is rejected; every
run has a timeout and is killed if it overruns; and the Docker runner disables networking by default
and can cap memory. sandrun runs code you are evaluating — treat the inputs as untrusted and prefer the
Docker runner for anything you do not control.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Fifteen tests covering the runner (pass, fail, timeout, working directory, empty command), the
workspace and harness (materialise/cleanup, overlay overwrite, path-traversal rejection, and an
end-to-end "the agent's fix makes the test pass"), the Docker argv builder, and the CLI. The Docker
argv is unit-tested without needing Docker. CI runs on Linux and Windows across Python 3.10–3.13.

## Project layout

```
src/sandrun
├── result.py     RunResult (+ passed / summary)
├── workspace.py  build & clean a throwaway workspace
├── runner.py     run a command locally with a timeout
├── docker.py     build/run a docker invocation (network off by default)
├── harness.py    run_in_sandbox: files + overlay + command
└── cli.py        run a command in a sandboxed copy of a directory
tests/            pytest suite
```

## License

MIT
