"""Installed CLI routing for `project --entity <id> --update <source>`.

The project proxy injects the CSV repository, so a valid route reaches the
run stage. With no annotation row for the identifier, the update fails with
a lookup error.
"""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimProjectEntityUpdateCommand:

    def test_project_help_lists_entity_update_command(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("project")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--update" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--entity", "abc"),
            ("--update", "title=New"),
            ("--entity", "--update"),
            ("--entity", "abc", "--update"),
            ("--update", "title=New", "--entity"),
            ("--entity", "abc", "--update", "title=New", "extra"),
            ("--entity", "abc", "--update", "title=New", "--unknown", "value"),
            ("--entity", "abc", "--entity", "def", "--update", "title=New"),
        ],
    )
    def test_invalid_entity_update_route_does_not_modify_entities(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("project", *args)

        assert result.exit_code != 0, result.stdout
        assert "Entity Updated" not in result.stdout
        assert workspace.snapshot() == before

    def test_valid_entity_update_route_reaches_run_and_fails_for_unknown_entity(
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
            "--update",
            "title=New",
        )

        assert result.exit_code != 0
        output: str = result.stdout + result.stderr
        assert "Run Exception" in output
        assert "No entity the container keeps has the global id" in output
        assert workspace.snapshot() == before

    def test_valid_entity_update_route_accepts_json_and_csv_sources(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        for source in ('{"title": "New"}', "title=New,text=Body"):
            result: CliInvocationResult = cli_runner.run(
                "project",
                "--global-id",
                workspace.selector("id"),
                "--entity",
                "abc",
                "--update",
                source,
            )
            assert result.exit_code != 0
            assert "No entity the container keeps has the global id" in (
                result.stdout + result.stderr
            )

        assert workspace.snapshot() == before
