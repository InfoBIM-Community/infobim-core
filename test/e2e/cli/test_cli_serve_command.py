"""Installed CLI routing for `infobim serve`.

The serve command starts a long-lived HTTP server on 127.0.0.1:8765. The
valid route is exercised by launching the server as a subprocess, pinging
its ``/ping`` endpoint, and terminating it.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


def _infobim_executable() -> Path:
    return Path(sys.executable).parent / "infobim"


def _test_environment() -> Dict[str, str]:
    environment: Dict[str, str] = dict(os.environ)
    environment.pop("ONTOBDC_PROJECT_ROOT", None)
    environment.pop("INFOBIM_PROJECT_ROOT", None)
    repository: Path = Path(__file__).resolve().parents[2]
    source_paths: List[str] = [str(repository / "src"), str(repository)]
    if "PYTHONPATH" in environment:
        source_paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(source_paths)
    return environment


class TestInfobimServeCommand:
    HOST: str = "127.0.0.1"
    PORT: int = 8765
    PING_URL: str = f"http://{HOST}:{PORT}/ping"

    def test_serve_starts_a_server_that_answers_ping(
        self, tmp_path: Path
    ) -> None:
        process: subprocess.Popen = subprocess.Popen(
            [str(_infobim_executable()), "serve", "--json"],
            cwd=tmp_path,
            env=_test_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            payload: Dict[str, Any] = self._wait_for_ping()
            assert payload["status"] == "ok"
            assert payload["app"] == "infobim"
            assert isinstance(payload["version"], str)
            assert payload["version"]
        finally:
            process.terminate()
            process.wait(timeout=10)

    def test_serve_returns_404_for_unknown_paths(
        self, tmp_path: Path
    ) -> None:
        process: subprocess.Popen = subprocess.Popen(
            [str(_infobim_executable()), "serve", "--json"],
            cwd=tmp_path,
            env=_test_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            self._wait_for_ping()
            try:
                urlopen(f"http://{self.HOST}:{self.PORT}/unknown", timeout=2)
                raise AssertionError("Expected 404 for unknown path")
            except HTTPError as exc:
                assert exc.code == 404
        finally:
            process.terminate()
            process.wait(timeout=10)

    def _wait_for_ping(self, attempts: int = 20, delay: float = 0.25) -> Dict[str, Any]:
        for _ in range(attempts):
            try:
                with urlopen(self.PING_URL, timeout=2) as response:
                    assert response.status == 200
                    return json.loads(response.read().decode("utf-8"))
            except (URLError, ConnectionError):
                time.sleep(delay)
        raise AssertionError(f"Server did not answer {self.PING_URL} in time")

    @pytest.mark.parametrize(
        "args",
        [
            ("serve", "extra"),
            ("serve", "--help"),
            ("serve", "--unknown"),
        ],
    )
    def test_serve_with_extra_arguments_does_not_start_a_server(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run(*args)

        assert result.exit_code != 0, result.stdout
        assert "Serve" not in result.stdout
