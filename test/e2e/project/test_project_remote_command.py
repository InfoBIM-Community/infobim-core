"""Installed CLI routing for `project --remote <url>`.

The remote project command runs the same download machine the OntoBDC
container remote command runs. An address that is not an http or https URL
is refused at the check stage; a syntactically valid URL that cannot be
downloaded fails at the run stage.
"""

from pathlib import Path
from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimProjectRemoteCommand:

    def test_project_help_lists_remote_command(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("project")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--remote" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--remote",),
            ("--remote", ""),
            ("--remote", "   "),
            ("--remote", "http://example.com/file.obdc", "extra"),
        ],
    )
    def test_remote_rejects_routing_invalid_arguments(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run("project", *args)

        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" in result.stdout

    @pytest.mark.parametrize(
        "url",
        [
            "not-a-url",
            "ftp://example.com/file.obdc",
        ],
    )
    def test_remote_rejects_invalid_urls_without_downloading(
        self,
        cli_runner: InfobimCliProcessRunner,
        url: str,
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run("project", "--remote", url)

        assert result.exit_code != 0
        assert "Invalid remote project URL" in result.stdout

    def test_remote_valid_url_reaches_the_download_stage(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "project", "--remote", "http://127.0.0.1:1/nonexistent.obdc"
        )

        assert result.exit_code != 0
        assert "RemoteFileDownloadError" in result.stdout + result.stderr
        downloaded: Path = tmp_path / "nonexistent.obdc"
        assert not downloaded.exists()
