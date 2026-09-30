from pathlib import Path
from typing import Any, Dict, List

import pytest

from test.e2e.project_workspace import ProjectE2eWorkspace
from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from infobim.project.plugin.command.inspect import ProjectInspectCommand
from infobim.project.plugin.command.interactive_inspect import (
    ProjectInteractiveInspectCommand,
)


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

    def test_inspect_by_global_id_identifier(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--inspect"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project"

    def test_inspect_by_path_identifier(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--inspect"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project"

    @pytest.mark.parametrize("interactive_flag", ["--interactive", "-i"])
    def test_inspect_leaves_interactive_flag_to_interactive_command(
        self, interactive_flag: str
    ) -> None:
        arguments: List[str] = [
            "project",
            "--global-id",
            "urn:uuid:00000000-0000-0000-0000-000000000000",
            "--inspect",
            interactive_flag,
        ]

        assert not ProjectInspectCommand.accepts(arguments)
        assert ProjectInteractiveInspectCommand.accepts(arguments)

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
