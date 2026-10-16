"""Installed CLI routing for `project --entity <id> --delete`.

Unlike OntoBDC's container entity delete, the project proxy injects the
CSV repository that keeps a project's entities, so a valid route reaches
the run stage. With no annotation rows for the identifier, deletion fails
with a lookup error rather than a repository-not-injected error.
"""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimProjectEntityDeleteCommand:

    def test_project_help_lists_entity_delete_command(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("project")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--delete" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--entity", "abc"),
            ("--entity", "--delete"),
            ("--entity", "abc", "--delete", "extra"),
            ("--entity", "abc", "--delete", "--unknown", "value"),
            ("--entity", "abc", "--entity", "def", "--delete"),
        ],
    )
    def test_invalid_entity_delete_route_does_not_remove_entities(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("project", *args)

        assert result.exit_code != 0, result.stdout
        assert "Entity Deleted" not in result.stdout
        assert workspace.snapshot() == before

    def test_valid_entity_delete_route_reaches_run_and_fails_for_unknown_entity(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "project",
            "--global-id",
            workspace.selector("id"),
            "--entity",
            "abc",
            "--delete",
        )

        assert result.exit_code != 0
        output: str = result.stdout + result.stderr
        assert "Run Exception" in output
        assert "No entity the container keeps has the global id" in output
        assert workspace.snapshot() == before

    def test_valid_entity_delete_route_from_project_directory(
        self,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = workspace.runner().run(
            "project", "--entity", "abc", "--delete"
        )

        assert result.exit_code != 0
        assert "No entity the container keeps has the global id" in (
            result.stdout + result.stderr
        )
        assert workspace.snapshot() == before
