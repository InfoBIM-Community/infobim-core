"""Installed CLI routing for `infobim drawing` (base/help command)."""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimDrawingBaseCommand:

    def test_drawing_without_arguments_lists_drawing_commands(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("drawing")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Drawing Commands"
        assert result.json["description"] == "Available drawing-domain utilities."
        assert "Usage" in result.json["content"]
        assert "Commands" in result.json["content"]

    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_drawing_help_flags_return_the_command_tree(
        self, cli_runner: InfobimCliProcessRunner, flag: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run("drawing", flag)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Drawing Commands"

    @pytest.mark.parametrize(
        "args",
        [
            ("--unknown",),
            ("--help", "--extra"),
        ],
    )
    def test_drawing_with_extra_arguments_fails(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("drawing", *args)

        assert result.exit_code != 0, result.stdout
        assert "Drawing Commands" not in result.stdout
