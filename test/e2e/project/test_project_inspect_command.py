from pathlib import Path
from typing import Any, Dict

import pytest

from test.e2e.project_workspace import ProjectE2eWorkspace
from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimProjectInspectCommand:

    def test_inspect_renders_project_metadata_as_static_tree(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--inspect"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        payload: Dict[str, Any] = result.json
        assert payload["title"] == "InfoBIM Project"
        assert workspace.project.name in payload["description"]
        assert "tree" in payload["content"]
        assert isinstance(payload["content"]["tree"], dict)

    @pytest.mark.parametrize("selector", ["storage_id", "ifc_global_id"])
    def test_inspect_by_global_id_identifier(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path, selector: str
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        identifier: str = (
            workspace.identifier if selector == "storage_id" else workspace.global_id()
        )
        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", identifier, "--inspect"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project"

    def test_inspect_from_project_directory(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = workspace.runner().run(
            "project", "--inspect"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project"


    def test_inspect_requires_a_project(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "project",
            "--global-id",
            "urn:uuid:00000000-0000-0000-0000-000000000000",
            "--inspect",
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
