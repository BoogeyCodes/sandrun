from __future__ import annotations

import json
import sys

import pytest
from fastapi.testclient import TestClient

from sandrun.service import create_app

PY = sys.executable
# For the /submit form tests the command is parsed with shlex (POSIX), which treats backslashes as
# escapes — so use forward slashes in the executable path (Windows accepts them).
PY_FWD = PY.replace("\\", "/")


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(":memory:")) as c:
        yield c


def test_healthz(client: TestClient):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_api_run_passes(client: TestClient):
    r = client.post("/api/runs", json={"command": [PY, "-c", "print('ok')"], "label": "hello"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "passed"
    assert body["passed"] is True
    assert body["exit_code"] == 0
    assert body["id"] == 1


def test_api_run_failure_is_stored(client: TestClient):
    r = client.post("/api/runs", json={"command": [PY, "-c", "import sys; sys.exit(3)"]})
    assert r.status_code == 201
    assert r.json()["status"] == "failed"
    assert r.json()["exit_code"] == 3


def test_api_run_with_files_and_tests(client: TestClient):
    files = {
        "calc.py": "def add(a, b):\n    return a + b\n",
        "test_calc.py": "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    }
    r = client.post("/api/runs", json={"command": [PY, "-m", "pytest", "-q"], "files": files, "label": "calc suite"})
    assert r.status_code == 201
    assert r.json()["status"] == "passed"

    detail = client.get(f"/api/runs/{r.json()['id']}")
    assert detail.status_code == 200
    assert "passed" in detail.json()["stdout"] or "1 passed" in detail.json()["stdout"]


def test_api_run_timeout(client: TestClient):
    r = client.post("/api/runs", json={"command": [PY, "-c", "import time; time.sleep(5)"], "timeout": 0.5})
    assert r.status_code == 201
    assert r.json()["status"] == "timeout"
    assert r.json()["timed_out"] is True


def test_api_run_rejects_empty_command(client: TestClient):
    assert client.post("/api/runs", json={"command": []}).status_code == 422


def test_api_list_and_filter(client: TestClient):
    client.post("/api/runs", json={"command": [PY, "-c", "print(1)"]})
    client.post("/api/runs", json={"command": [PY, "-c", "import sys; sys.exit(1)"]})
    assert len(client.get("/api/runs").json()) == 2
    passed = client.get("/api/runs", params={"status": "passed"}).json()
    assert len(passed) == 1 and passed[0]["status"] == "passed"


def test_api_stats(client: TestClient):
    client.post("/api/runs", json={"command": [PY, "-c", "print(1)"]})
    client.post("/api/runs", json={"command": [PY, "-c", "import sys; sys.exit(1)"]})
    s = client.get("/api/stats").json()
    assert s["total"] == 2
    assert s["passed"] == 1
    assert s["pass_rate"] == 0.5


def test_missing_run_is_404(client: TestClient):
    assert client.get("/api/runs/999").status_code == 404
    assert client.get("/runs/999").status_code == 404


def test_run_html_page(client: TestClient):
    rid = client.post("/api/runs", json={"command": [PY, "-c", "print('hey')"], "label": "demo"}).json()["id"]
    page = client.get(f"/runs/{rid}")
    assert page.status_code == 200
    assert "demo" in page.text
    assert "stdout" in page.text


def test_submit_form_runs_and_redirects(client: TestClient):
    r = client.post(
        "/submit",
        data={"command": f"{PY_FWD} -c \"print('form run')\"", "files": "", "timeout": "30"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].startswith("/runs/")


def test_submit_form_bad_files_json(client: TestClient):
    r = client.post(
        "/submit",
        data={"command": "echo hi", "files": "{not json", "timeout": "30"},
        follow_redirects=False,
    )
    assert r.status_code == 400
    assert "json" in r.text.lower()


def test_submit_form_with_files(client: TestClient):
    files = json.dumps({"m.py": "print('from file')"})
    r = client.post(
        "/submit",
        data={"command": f"{PY_FWD} m.py", "files": files, "timeout": "30"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "from file" in r.text


def test_index_renders(client: TestClient):
    assert client.get("/").status_code == 200
