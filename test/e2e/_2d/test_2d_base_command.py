"""Installed CLI routing for `infobim 2d` (base/help command)."""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimTwoDBaseCommand:

    def test_2d_without_arguments_lists_2d_commands(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("2d")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "2D Commands"
        assert result.json["description"] == "Available 2D drawing utilities."
        assert "Usage" in result.json["content"]
        assert "Commands" in result.json["content"]

    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_2d_help_flags_return_the_command_tree(
        self, cli_runner: InfobimCliProcessRunner, flag: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run("2d", flag)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "2D Commands"

    @pytest.mark.parametrize(
        "expected",
        [
            "--help",
            "--enable",
        ],
    )
    def test_2d_help_lists_every_2d_command_flag(
        self, cli_runner: InfobimCliProcessRunner, expected: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run("2d")

        assert result.exit_code == 0
        assert expected in result.stdout

    def test_2d_does_not_handle_enable_flag(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        """
        ``--enable`` is owned by ``TwoDEnableCommand``; the base command must
        not claim it.
        """
        result: CliInvocationResult = cli_runner.run("2d", "--enable", "extra")

        assert result.exit_code != 0, result.stdout
        assert "2D Commands" not in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--unknown",),
            ("--help", "--extra"),
        ],
    )
    def test_2d_with_extra_arguments_fails(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("2d", *args)

        assert result.exit_code != 0, result.stdout
        assert "2D Commands" not in result.stdout
