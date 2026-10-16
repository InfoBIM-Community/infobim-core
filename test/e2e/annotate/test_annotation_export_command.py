"""Installed CLI routing for `infobim annotate --export excel --type <type>`."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimAnnotationExportCommand:

    def test_export_excel_writes_a_workbook_for_a_type(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        created: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--type",
            "note",
            "--title",
            "Export me",
        )
        assert created.exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--export",
            "excel",
            "--type",
            "note",
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Annotations Exported"
        assert result.json["content"]["format"] == "excel"
        assert result.json["content"]["items"] == 1

    def test_export_rejects_unknown_format(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--export",
            "csv",
            "--type",
            "note",
        )

        assert result.exit_code != 0
        assert "is not an export format" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--export", "excel"),
            ("--type", "note"),
            ("--export",),
            ("--export", "excel", "--type"),
            ("--export", "excel", "--type", "note", "extra"),
            ("--export", "excel", "--type", "note", "--unknown", "value"),
        ],
    )
    def test_invalid_export_route_does_not_export(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("annotate", *args)

        assert result.exit_code != 0, result.stdout
        assert "Annotations Exported" not in result.stdout
        assert workspace.snapshot() == before
