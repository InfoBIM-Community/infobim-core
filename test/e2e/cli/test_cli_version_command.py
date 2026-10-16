"""Installed CLI routing for `infobim --version` / `infobim -v`."""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimVersionCommand:

    @pytest.mark.parametrize("flag", ["--version", "-v"])
    def test_version_flags_report_the_infobim_distribution_version(
        self, cli_runner: InfobimCliProcessRunner, flag: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run(flag)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Version"
        assert isinstance(result.json["content"]["version"], str)
        assert result.json["content"]["version"]

    @pytest.mark.parametrize(
        "args",
        [
            ("--version", "extra"),
            ("-v", "--version"),
            ("--version", "--extra"),
        ],
    )
    def test_version_with_extra_arguments_fails(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run(*args)

        assert result.exit_code != 0, result.stdout
        assert "InfoBIM Version" not in result.stdout
