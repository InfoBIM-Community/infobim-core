"""Installed CLI routing for `project --entity` (entity listing).

The project entity command is a proxy over OntoBDC's container entity
listing. What InfoBIM adds is the project selector (``--global-id``) and
the guard that the selected container is a project.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimProjectEntityCommand:

    def test_project_help_lists_entity_command(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("project")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--entity" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--entity", "value"),
            ("--entity", "--unknown"),
            ("--global-id",),
            ("--global-id", "id", "--entity", "extra"),
            ("--entity", "--global-id"),
        ],
    )
    def test_invalid_entity_route_fails_without_listing_entities(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("project", *args)
        assert result.exit_code != 0, result.stdout
        assert "Container Entities" not in result.stdout

    def test_entity_lists_datasets_of_a_registered_project(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--entity"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Container Entities"
        datasets: List[Dict[str, Any]] = result.json["content"]["datasets"]
        assert isinstance(datasets, list)
        assert workspace.snapshot() == before

    def test_entity_resolves_project_from_current_directory(
        self,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = workspace.runner().run("project", "--entity")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Container Entities"
        assert workspace.snapshot() == before
