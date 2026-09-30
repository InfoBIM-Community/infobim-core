from typing import Any, Dict, Tuple
from pathlib import Path

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimProjectDatasetCommand:

    def test_create_dataset_builds_a_new_dataset_inside_the_project(
        self, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = workspace.runner().run(
            "project",
            "--global-id",
            workspace.selector("id"),
            "--create-dataset",
            "Measurements",
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        payload: Dict[str, Any] = result.json
        assert payload["severity"] is None
        dataset_dir: Path = workspace.project / "measurements"
        assert dataset_dir.is_dir()
        assert (dataset_dir / ".__ontobdc__" / "dataset.ttl").is_file()

    def test_create_dataset_by_project_identifier(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run(
            "project",
            "--global-id",
            workspace.selector("id"),
            "--create-dataset",
            "Drawings",
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert (workspace.project / "drawings" / ".__ontobdc__").is_dir()

    def test_create_dataset_without_a_title_is_rejected(
        self, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = workspace.runner().run(
            "project", "--create-dataset"
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"

    @pytest.mark.parametrize(
        "arguments",
        [
            ("--global-id", "--create-dataset", "title"),
        ],
    )
    def test_create_dataset_rejects_selector_without_a_value(
        self,
        tmp_path: Path,
        arguments: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        result: CliInvocationResult = workspace.runner().run("project", *arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
