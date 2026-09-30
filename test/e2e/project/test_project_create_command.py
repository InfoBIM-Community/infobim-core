from pathlib import Path
from typing import Any, Dict, List

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimProjectCreateCommand:

    def test_create_builds_a_new_project(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        cli_runner.run("init")
        result: CliInvocationResult = cli_runner.run(
            "project", "--create", "My New Project"
        )

        assert result.exit_code == 0, result.stdout + result.stderr

        payload: Dict[str, Any] = result.json
        assert payload["severity"] is None

        expected_path: Path = (tmp_path / "my-new-project").resolve()
        content: Dict[str, Any] = payload["content"]
        assert Path(content["path"]).resolve() == expected_path
        assert content["exists"] is True

        project_directory: Path = tmp_path / "my-new-project"
        assert (project_directory / ".__infobim__").is_dir()
        assert (project_directory / ".__ontobdc__" / "container.ttl").is_file()

    def test_create_registers_the_project_in_the_storage_index(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        cli_runner.run("init")
        cli_runner.run("project", "--create", "My New Project")

        list_result: CliInvocationResult = cli_runner.run("project", "--list")

        assert list_result.exit_code == 0, list_result.stdout + list_result.stderr
        projects: List[Dict[str, Any]] = list_result.json["content"]["projects"]
        assert len(projects) == 1
        assert (
            Path(projects[0]["location"]).resolve()
            == (tmp_path / "my-new-project").resolve()
        )

    def test_create_without_a_name_is_rejected(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        cli_runner.run("init")
        result: CliInvocationResult = cli_runner.run("project", "--create")

        assert result.exit_code == 1

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Run Exception"
