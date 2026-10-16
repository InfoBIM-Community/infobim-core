"""Installed CLI routing for `infobim ifc` (base/help command)."""

from typing import Any, Dict, List, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimIfcBaseCommand:

    def test_ifc_without_arguments_lists_ifc_commands(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("ifc")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "IFC Commands"
        assert result.json["description"] == "Available IFC file utilities."
        assert "Usage" in result.json["content"]
        assert "Commands" in result.json["content"]

    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_ifc_help_flags_return_the_command_tree(
        self, cli_runner: InfobimCliProcessRunner, flag: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run("ifc", flag)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "IFC Commands"

    @pytest.mark.parametrize(
        "expected",
        [
            "--health",
            "--global-id",
            "--term",
            "--point",
            "--ifc-model-path",
        ],
    )
    def test_ifc_help_lists_every_ifc_command_flag(
        self, cli_runner: InfobimCliProcessRunner, expected: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run("ifc")

        assert result.exit_code == 0
        assert expected in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--unknown",),
            ("--health", "--extra"),
            ("--term", "wall", "--point", "drawing.dxf", "extra"),
        ],
    )
    def test_ifc_with_extra_arguments_fails(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("ifc", *args)

        assert result.exit_code != 0, result.stdout
        assert "IFC Commands" not in result.stdout
