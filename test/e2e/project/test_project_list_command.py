from typing import Any, Dict, List
from pathlib import Path

from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
    main as prepare_metadata,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
    main as prepare_storage_index,
)

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimProjectListCommand:

    def test_list_returns_empty_when_no_project_is_registered(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run("project", "--list")

        assert result.exit_code == 0, result.stdout + result.stderr
        payload: Dict[str, Any] = result.json
        assert payload["title"] == "InfoBIM Projects"
        assert payload["severity"] is None
        assert payload["content"]["projects"] == []

    def test_short_list_flag_returns_empty_when_no_project_is_registered(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run("project", "-l")

        assert result.exit_code == 0
        assert result.json["content"]["projects"] == []

    def test_list_includes_an_existing_project(
        self, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        runner: InfobimCliProcessRunner = InfobimCliProcessRunner(tmp_path)

        result: CliInvocationResult = runner.run("project", "--list")

        assert result.exit_code == 0, result.stdout + result.stderr
        projects: List[Dict[str, Any]] = result.json["content"]["projects"]
        assert len(projects) == 1
        assert projects[0]["id"] == workspace.identifier
        assert (
            Path(projects[0]["location"]).resolve() == workspace.project.resolve()
        )

    def test_list_excludes_plain_containers_that_are_not_projects(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        cli_runner.run("init")
        plain_container: Path = tmp_path / "just-a-container"
        plain_container.mkdir()
        prepare_metadata(container_path=str(plain_container), root_path=str(tmp_path))
        prepare_storage_index(container_path=str(plain_container), root_path=str(tmp_path))

        result: CliInvocationResult = cli_runner.run("project", "--list")

        assert result.exit_code == 0
        assert result.json["content"]["projects"] == []
