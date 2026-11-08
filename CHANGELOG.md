# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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
