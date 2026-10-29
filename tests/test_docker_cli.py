from __future__ import annotations

import sys
from pathlib import Path

from sandrun.cli import main
from sandrun.docker import build_docker_argv

PY = sys.executable


class TestDockerArgv:
    def test_defaults_rm_workdir_mount_and_no_network(self, tmp_path: Path):
        argv = build_docker_argv("python:3.12", ["pytest", "-q"], mount=tmp_path)
        assert argv[:3] == ["docker", "run", "--rm"]
        assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
        assert "-w" in argv and argv[argv.index("-w") + 1] == "/work"
        assert argv[-3:] == ["python:3.12", "pytest", "-q"]
        assert any(part.endswith(":/work") for part in argv)

    def test_env_and_memory_and_network_override(self, tmp_path: Path):
        argv = build_docker_argv(
            "img", ["echo", "hi"], mount=tmp_path, network=None, memory="256m", env={"CI": "1"}
        )
        assert "--network" not in argv
        assert "--memory" in argv and argv[argv.index("--memory") + 1] == "256m"
        assert "-e" in argv and "CI=1" in argv


class TestCli:
    def test_runs_command_in_sandbox_copy(self, tmp_path: Path, capsys):
        (tmp_path / "hello.py").write_text("print('from sandbox')")
        code = main(["--dir", str(tmp_path), "--", PY, "hello.py"])
        captured = capsys.readouterr()
        assert code == 0
        assert "from sandbox" in captured.out
        assert "PASS" in captured.err

    def test_failing_command_returns_one(self, tmp_path: Path, capsys):
        code = main(["--dir", str(tmp_path), "--", PY, "-c", "import sys; sys.exit(2)"])
        assert code == 1
        assert "FAIL" in capsys.readouterr().err

    def test_no_command_is_error(self, tmp_path: Path, capsys):
        assert main(["--dir", str(tmp_path)]) == 2
        assert "no command" in capsys.readouterr().err

    def test_bad_dir_is_error(self, capsys):
        assert main(["--dir", "does-not-exist", "--", "echo", "x"]) == 2
