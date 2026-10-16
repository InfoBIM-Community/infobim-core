"""Installed CLI routing for `infobim annotate` (base/help command)."""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimAnnotationBaseCommand:

    def test_annotate_without_arguments_lists_annotation_commands(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("annotate")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Annotation Commands"
        assert "Usage" in result.json["content"]
        assert "Commands" in result.json["content"]

    @pytest.mark.parametrize("flag", ["--help", "-h"])
    def test_annotate_help_flags_return_the_command_tree(
        self, cli_runner: InfobimCliProcessRunner, flag: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run("annotate", flag)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Annotation Commands"

    @pytest.mark.parametrize(
        "expected",
        [
            "--list",
            "--guid",
            "--delete",
            "--clear",
            "--export",
            "--type",
            "--title",
        ],
    )
    def test_annotate_help_lists_every_annotation_command_flag(
        self, cli_runner: InfobimCliProcessRunner, expected: str
    ) -> None:
        result: CliInvocationResult = cli_runner.run("annotate")

        assert result.exit_code == 0
        assert expected in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--unknown",),
            ("--list", "--extra"),
            ("--guid", "abc", "--delete", "extra"),
        ],
    )
    def test_annotate_with_extra_arguments_fails(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("annotate", *args)

        assert result.exit_code != 0, result.stdout
        assert "Annotation Commands" not in result.stdout
