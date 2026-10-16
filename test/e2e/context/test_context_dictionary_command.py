"""Installed CLI routing for `infobim context --term <value> --inspect`."""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimContextDictionaryCommand:
    """
    ``context --term <value> --inspect`` runs the dictionary-inspection
    pipeline on a term.

    The pipeline needs the stanza language models for lemmatization; without them
    (offline environment) the run stops at ``TEXT_LEMMATIZED``. That stop
    proves the command was accepted and started executing.
    """

    def test_context_inspect_reaches_execution(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "context", "--term", "wall", "--inspect"
        )

        assert result.exit_code != 0
        assert result.json["title"] == "Run Exception"
        assert "TEXT_LEMMATIZED" in result.json["content"]["error"]

    def test_context_inspect_accepts_inspect_before_term(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "context", "--inspect", "--term", "wall"
        )

        assert result.exit_code != 0
        assert result.json["title"] == "Run Exception"
        assert "TEXT_LEMMATIZED" in result.json["content"]["error"]

    @pytest.mark.parametrize(
        "args",
        [
            (),
            ("--term", "wall"),
            ("--inspect",),
            ("--term",),
            ("--inspect", "--term"),
            ("--term", "wall", "--inspect", "extra"),
            ("--term", "wall", "--unknown", "value"),
            ("--term", "", "--inspect"),
            ("--term", "   ", "--inspect"),
        ],
    )
    def test_invalid_context_route_does_not_inspect(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context", *args)

        assert result.exit_code != 0, result.stdout
        assert "TEXT_LEMMATIZED" not in result.stdout
