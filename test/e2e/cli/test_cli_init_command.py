"""Installed CLI routing for `infobim init`."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimInitCommand:

    def test_init_creates_an_ontobdc_project_in_the_current_directory(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        result: CliInvocationResult = cli_runner.run("init")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Init"
        assert result.json["description"] == "InfoBIM initialization executed successfully."
        assert result.json["content"]["root_path"] == str(tmp_path)
        assert (tmp_path / ".__ontobdc__").is_dir()

    def test_init_is_idempotent_on_an_already_initialized_directory(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        first: CliInvocationResult = cli_runner.run("init")
        assert first.exit_code == 0

        second: CliInvocationResult = cli_runner.run("init")
        assert second.exit_code == 0, second.stdout + second.stderr
        assert second.json["title"] == "Init"
        assert (tmp_path / ".__ontobdc__").is_dir()

    @pytest.mark.parametrize(
        "args",
        [
            ("init", "extra"),
            ("init", "--help"),
            ("init", "--unknown"),
        ],
    )
    def test_init_with_extra_arguments_fails_without_creating_files(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        before: Dict[str, Any] = {p.name for p in tmp_path.iterdir()}

        result: CliInvocationResult = cli_runner.run(*args)

        assert result.exit_code != 0, result.stdout
        assert result.json["title"] == "Run Exception"
        assert {p.name for p in tmp_path.iterdir()} == before
