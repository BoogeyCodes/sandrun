"""A FastAPI web service and REST API around the sandbox runner.

This is the optional web layer (``pip install sandrun[web]``). The runner core stays dependency-free;
only this module needs FastAPI, Uvicorn and Jinja2.

    from sandrun.service import create_app
    app = create_app("sandrun.db")      # pass to uvicorn, or use `sandrun serve`

Submit a run (a set of files plus a command); it executes in a throwaway sandbox — locally, or inside
a Docker image if you name one and Docker is available — and the result (verdict, timing, logs) is
stored and shown on a dashboard.

Routes:
    GET  /                    dashboard: pass-rate stats, recent runs, submit form
    POST /submit              (form) submit a run, redirect to its page
    GET  /runs/{id}           HTML page for one run (verdict, timing, logs)
    POST /runs/{id}/delete    delete it (HTMX), redirect home
    POST /api/runs            REST: submit a run, get the stored result back (201)
    GET  /api/runs            REST: list run summaries (optional ?status=)
    GET  /api/runs/{id}       REST: one run with its logs
    GET  /api/stats           REST: pass/fail/timeout counts and pass rate
    GET  /healthz             liveness probe

Security note: the local runner executes the command on the host (inside a throwaway *directory*, not a
container). Bind to localhost, and use the Docker mode (name an ``image``) for untrusted code.
"""

from __future__ import annotations

import shlex
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from sandrun import __version__
from sandrun.docker import docker_available, run_docker
from sandrun.harness import run_in_sandbox
from sandrun.result import RunResult
from sandrun.store import RunStore, status_of
from sandrun.workspace import workspace

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class RunRequest(BaseModel):
    command: list[str] = Field(..., min_length=1, description="argv to run, e.g. ['pytest', '-q']")
    files: dict[str, str] = Field(default_factory=dict, description="starting files: path -> content")
    overlay: dict[str, str] = Field(default_factory=dict, description="changes applied on top of files")
    timeout: float = Field(default=120.0, gt=0, description="seconds before the command is killed")
    label: str = Field(default="", description="a short label for the run")
    image: str | None = Field(default=None, description="Docker image to run in (needs Docker)")


def execute(
    files: Mapping[str, str],
    command: Sequence[str],
    overlay: Mapping[str, str] | None = None,
    timeout: float = 120.0,
    image: str | None = None,
) -> tuple[RunResult, str]:
    """Run a submission in a sandbox and return ``(result, status)``.

    Uses Docker when an image is named and Docker is available; otherwise runs locally. Any failure to
    launch is caught and reported as an ``error`` status rather than crashing the request.
    """
    try:
        if image and docker_available():
            with workspace(files, overlay) as root:
                result = run_docker(image, command, mount=root, timeout=timeout)
        else:
            result = run_in_sandbox(files, command, overlay=overlay, timeout=timeout)
        return result, status_of(result)
    except Exception as exc:  # pragma: no cover - defensive; surfaces as an 'error' run
        return RunResult(list(command), None, 0.0, False, "", f"sandrun could not run the command: {exc}"), "error"


def create_app(db_path: str | Path = "sandrun.db") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.store = RunStore(db_path)
        try:
            yield
        finally:
            app.state.store.close()

    app = FastAPI(
        title="sandrun",
        version=__version__,
        description="Run an AI coding agent's work against tests in an isolated sandbox, and track pass rates.",
        lifespan=lifespan,
    )

    def store() -> RunStore:
        return app.state.store

    # -- HTML pages ------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "stats": store().stats(),
                "runs": store().list(limit=25),
                "docker": docker_available(),
                "version": __version__,
            },
        )

    @app.post("/submit")
    def submit(
        request: Request,
        command: str = Form(...),
        files: str = Form(default=""),
        timeout: float = Form(default=30.0),
        label: str = Form(default=""),
    ):
        import json

        error = None
        argv: list[str] = []
        parsed_files: dict[str, str] = {}
        try:
            argv = shlex.split(command)
            if not argv:
                raise ValueError("command is empty")
            if files.strip():
                parsed_files = json.loads(files)
                if not isinstance(parsed_files, dict):
                    raise ValueError("files must be a JSON object of path -> content")
        except (ValueError, json.JSONDecodeError) as exc:
            error = str(exc)

        if error is not None:
            return _TEMPLATES.TemplateResponse(
                request=request,
                name="index.html",
                context={
                    "request": request,
                    "stats": store().stats(),
                    "runs": store().list(limit=25),
                    "docker": docker_available(),
                    "version": __version__,
                    "error": error,
                    "command": command,
                    "files": files,
                },
                status_code=400,
            )

        result, status = execute(parsed_files, argv, timeout=timeout)
        stored = store().add(result, label=label or command, status=status)
        return RedirectResponse(f"/runs/{stored.id}", status_code=303)

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_page(request: Request, run_id: int) -> HTMLResponse:
        run = store().get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return _TEMPLATES.TemplateResponse(
            request=request,
            name="run.html",
            context={"request": request, "run": run, "version": __version__},
        )

    @app.post("/runs/{run_id}/delete")
    def delete_run(run_id: int):
        store().delete(run_id)
        return RedirectResponse("/", status_code=303)

    # -- JSON API --------------------------------------------------------
    @app.post("/api/runs")
    def api_create(req: RunRequest) -> JSONResponse:
        result, status = execute(req.files, req.command, overlay=req.overlay, timeout=req.timeout, image=req.image)
        stored = store().add(result, label=req.label, status=status)
        return JSONResponse(_run_json(stored), status_code=201)

    @app.get("/api/runs")
    def api_list(limit: int = 100, offset: int = 0, status: str | None = None) -> list[dict]:
        return [
            {
                "id": s.id,
                "created_at": s.created_at,
                "label": s.label,
                "command": s.command,
                "status": s.status,
                "exit_code": s.exit_code,
                "duration_s": round(s.duration_s, 3),
            }
            for s in store().list(limit=limit, offset=offset, status=status)
        ]

    @app.get("/api/runs/{run_id}")
    def api_get(run_id: int) -> dict:
        run = store().get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return _run_json(run, with_logs=True)

    @app.get("/api/stats")
    def api_stats() -> dict:
        s = store().stats()
        return {
            "total": s.total,
            "passed": s.passed,
            "failed": s.failed,
            "timeout": s.timeout,
            "error": s.error,
            "pass_rate": s.pass_rate,
            "avg_duration_s": s.avg_duration_s,
        }

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "version": __version__, "runs": store().count(), "docker": docker_available()}

    return app


def _run_json(run, with_logs: bool = False) -> dict:
    body = {
        "id": run.id,
        "created_at": run.created_at,
        "label": run.label,
        "command": run.command,
        "status": run.status,
        "passed": run.passed,
        "exit_code": run.exit_code,
        "duration_s": round(run.duration_s, 3),
        "timed_out": run.timed_out,
    }
    if with_logs:
        body["stdout"] = run.stdout
        body["stderr"] = run.stderr
    return body
