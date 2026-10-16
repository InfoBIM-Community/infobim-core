"""Installed CLI routing for `infobim ifc --health`."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimIfcHealthCommand:

    def test_health_reports_healthy_when_project_has_no_ifc_models(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "ifc", "--global-id", workspace.selector("id"), "--health"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "IFC Health"
        assert result.json["severity"] == "SUCCESS"
        assert result.json["content"]["healthy"] is True
        assert result.json["content"]["models"] == []
        assert result.json["content"]["checks"] == []
        assert workspace.snapshot() == before

    def test_health_resolves_project_from_current_directory(
        self,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = workspace.runner().run("ifc", "--health")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "IFC Health"
        assert result.json["content"]["healthy"] is True

    def test_health_with_nonexistent_ifc_model_path_fails(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "ifc",
            "--global-id",
            workspace.selector("id"),
            "--health",
            "--ifc-model-path",
            "/nonexistent/model.ifc",
        )

        assert result.exit_code != 0
        assert result.json["title"] == "Run Exception"
        assert "is not an IFC model file" in result.json["content"]["error"]
        assert workspace.snapshot() == before

    def test_health_requires_a_project(
        self,
        cli_runner: InfobimCliProcessRunner,
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "ifc",
            "--global-id",
            "urn:uuid:00000000-0000-0000-0000-000000000000",
            "--health",
        )

        assert result.exit_code != 0
        assert result.json["title"] == "Run Exception"

    @pytest.mark.parametrize(
        "args",
        [
            ("--health", "extra"),
            ("--global-id", "--health"),
            ("--health", "--ifc-model-path"),
            ("--global-id", "id", "--health", "extra"),
        ],
    )
    def test_invalid_health_route_does_not_report_health(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("ifc", *args)

        assert result.exit_code != 0, result.stdout
        assert "IFC Health" not in result.stdout
