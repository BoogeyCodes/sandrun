# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0]

Grows sandrun from a runner library into a sandbox-execution **service**: submit a run (files plus a
command), it executes in a throwaway sandbox, and the verdict, timing and logs are stored and shown on
a dashboard with a running pass rate. The runner core stays dependency-free; the web layer is an
optional extra (`pip install sandrun[web]`).

### Added
- `RunStore` — a dependency-free SQLite history of runs, with `add`, `get`, `list` (filterable by
  status), `delete`, `count` and `stats` (passed/failed/timeout counts, pass rate, average duration).
- `sandrun.service.create_app` — a FastAPI app: a dashboard (pass-rate stats, a submit form, recent
  runs), per-run pages with logs, and a JSON REST API (`POST/GET /api/runs`, `GET /api/runs/{id}`,
  `GET /api/stats`, `GET /healthz`). Runs execute locally, or in Docker when an image is named.
- `sandrun serve` CLI subcommand to run the dashboard + API (needs the `[web]` extra).
- `status_of(result)` helper mapping a `RunResult` onto passed/failed/timeout.
- A `Dockerfile` that serves the dashboard, persisting run history to a mounted volume.

### Changed
- Version bumped to 0.2.0; `[web]` optional-dependency group added.

## [0.1.x]

### Added
- `RunResult.head(lines=20)` — the first few lines of output, for failures that happen
  at startup (complements `tail`).
- `RunResult.combined_output` — stdout and stderr together.
- `RunResult.tail(lines=20)` — the last few lines of output, so an evaluation
  report can show why a run failed without embedding the entire log.

## [0.1.0]

### Added
- `RunResult` with a strict pass rule (finished in time, zero exit code).
- Local subprocess runner with a timeout.
- Sandbox workspace with path-traversal protection and a file overlay.
- Docker runner (`docker run --rm --network none`) and argv builder.
- `sandrun` CLI.
