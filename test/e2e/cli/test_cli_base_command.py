"""Installed CLI routing for `infobim cli` (CLI component base command)."""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimCliBaseCommand:

    def test_cli_without_arguments_lists_cli_commands(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("cli")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "CLI Commands"
        assert result.json["description"] == "Available CLI bootstrap/identity utilities."
        assert "Usage" in result.json["content"]
        assert "Commands" in result.json["content"]

    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_cli_help_flags_return_the_command_tree(
        self, cli_runner: InfobimCliProcessRunner, flag: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run("cli", flag)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "CLI Commands"

    @pytest.mark.parametrize("expected", ["init", "serve", "--version", "--help"])
    def test_cli_help_lists_every_cli_command(
        self, cli_runner: InfobimCliProcessRunner, expected: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run("cli")

        assert result.exit_code == 0
        assert expected in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("cli", "--unknown"),
            ("cli", "init", "--help"),
            ("cli", "extra"),
            ("cli", "--help", "extra"),
        ],
    )
    def test_cli_with_extra_arguments_fails(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run(*args)

        assert result.exit_code != 0, result.stdout
        assert "CLI Commands" not in result.stdout
