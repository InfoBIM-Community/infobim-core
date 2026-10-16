"""Installed CLI routing for the InfoBIM welcome command.

The welcome command owns the bare ``infobim`` invocation as well as the
global ``--help`` / ``-h`` flags. It renders the full InfoBIM command tree.
"""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimWelcomeCommand:

    def test_bare_executable_renders_the_infobim_command_tree(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run()

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Commands"
        assert result.json["description"] == "Available commands and options."
        assert "Usage" in result.json["content"]
        assert "Commands" in result.json["content"]

    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_global_help_flags_render_the_infobim_command_tree(
        self, cli_runner: InfobimCliProcessRunner, flag: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run(flag)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Commands"

    @pytest.mark.parametrize(
        "expected",
        [
            "2d",
            "annotate",
            "cli",
            "context",
            "drawing",
            "ifc",
            "project",
            "run",
        ],
    )
    def test_welcome_tree_lists_every_top_level_component(
        self, cli_runner: InfobimCliProcessRunner, expected: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run()

        assert result.exit_code == 0
        assert expected in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--help", "--extra"),
            ("--help", "extra"),
            ("-h", "--extra"),
        ],
    )
    def test_welcome_with_extra_arguments_fails(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run(*args)

        assert result.exit_code != 0, result.stdout
        assert "InfoBIM Commands" not in result.stdout
