"""Installed CLI routing for `infobim ifc --term <term> --point <drawing>`."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimIfcPointCommand:

    def test_point_with_valid_route_reaches_execution(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        """
        A correctly routed ``ifc --term --point`` passes the routing and
        project guards and reaches the element-creation state machine.

        The full happy path needs an interactive DXF viewer and the stanza
        language models; in a headless environment without those models the
        run stops at the text-lemmatization step. That stop is exactly what
        proves the command was accepted and started executing.
        """
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        drawing: Path = workspace.project / "drawing.dxf"
        drawing.write_text("0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n")

        result: CliInvocationResult = cli_runner.run(
            "ifc",
            "--global-id",
            workspace.selector("id"),
            "--term",
            "wall",
            "--point",
            str(drawing),
        )

        assert result.exit_code != 0
        assert result.json["title"] == "Run Exception"
        assert "TEXT_LEMMATIZED" in result.json["content"]["error"]

    def test_point_requires_a_project(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        assert cli_runner.run("init").exit_code == 0
        drawing: Path = tmp_path / "drawing.dxf"
        drawing.write_text("0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n")

        result: CliInvocationResult = cli_runner.run(
            "ifc",
            "--global-id",
            "urn:uuid:00000000-0000-0000-0000-000000000000",
            "--term",
            "wall",
            "--point",
            str(drawing),
        )

        assert result.exit_code != 0
        assert result.json["title"] == "Run Exception"

    @pytest.mark.parametrize(
        "args",
        [
            ("--term", "wall"),
            ("--point", "drawing.dxf"),
            ("--term",),
            ("--point",),
            ("--term", "wall", "--point"),
            ("--term", "--point", "drawing.dxf"),
            ("--term", "wall", "--point", "drawing.dxf", "extra"),
            ("--term", "wall", "--term", "other", "--point", "drawing.dxf"),
            ("--term", "wall", "--point", "drawing.dxf", "--unknown", "value"),
        ],
    )
    def test_invalid_point_route_does_not_start_execution(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("ifc", *args)

        assert result.exit_code != 0, result.stdout
        assert "IFC Elements Created" not in result.stdout
        assert workspace.snapshot() == before
