from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from test.e2e.cli_process_runner import (
    CliInvocationResult,
    InfobimCliProcessRunner,
)
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimProjectRefreshCommand:


    def test_refresh_synchronizes_added_files_and_preserves_user_content(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        measurements: Path = workspace.project / "measurements.csv"
        measurements.write_text("value\n42\n", encoding="utf-8")
        assert "measurements.csv" not in workspace.manifest_files()

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project Refreshed"
        content: Dict[str, Any] = result.json["content"]
        assert "container_visited_states" in content
        assert "project_visited_states" in content
        assert isinstance(content["container_visited_states"], list)
        assert isinstance(content["project_visited_states"], list)
        assert "measurements.csv" in workspace.manifest_files()
        assert measurements.read_bytes() == b"value\n42\n"

    def test_refresh_removes_stale_manifest_entries_after_a_file_is_deleted(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        removed: Path = workspace.project / "removed.csv"
        removed.write_text("value\n42\n", encoding="utf-8")
        synchronized: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )
        assert synchronized.exit_code == 0, synchronized.stdout
        assert "removed.csv" in workspace.manifest_files()
        removed.unlink()

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert "removed.csv" not in workspace.manifest_files()
        assert not removed.exists()

    def test_refresh_is_repeatable_without_duplicate_storage_entries(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        first: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )
        second: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout
        listing: CliInvocationResult = InfobimCliProcessRunner(workspace.root).run(
            "project", "--list"
        )
        assert listing.exit_code == 0, listing.stdout
        projects: List[Dict[str, Any]] = listing.json["content"]["projects"]
        assert [entry["id"] for entry in projects] == [workspace.identifier]

    def test_refresh_requires_a_project(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", "urn:uuid:00000000-0000-0000-0000-000000000000", "--refresh"
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"

    def test_refresh_infers_project_from_cwd_without_global_id(
        self,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        measurements: Path = workspace.project / "measurements.csv"
        measurements.write_text("value\n42\n", encoding="utf-8")
        assert "measurements.csv" not in workspace.manifest_files()

        result: CliInvocationResult = workspace.runner().run("project", "--refresh")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project Refreshed"
        content: Dict[str, Any] = result.json["content"]
        assert "container_visited_states" in content
        assert "project_visited_states" in content
        assert isinstance(content["container_visited_states"], list)
        assert isinstance(content["project_visited_states"], list)
        assert "measurements.csv" in workspace.manifest_files()
        assert measurements.read_bytes() == b"value\n42\n"

    def test_refresh_infers_project_from_subdirectory_inside_project(
        self,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        subdir: Path = workspace.project / "aux" / "data"
        subdir.mkdir(parents=True)
        (subdir / "notes.csv").write_text("note\nfirst\n", encoding="utf-8")

        runner_from_subdir: InfobimCliProcessRunner = InfobimCliProcessRunner(subdir)
        result: CliInvocationResult = runner_from_subdir.run("project", "--refresh")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project Refreshed"
        listing: CliInvocationResult = InfobimCliProcessRunner(workspace.root).run(
            "project", "--list"
        )
        assert listing.exit_code == 0, listing.stdout
        projects: List[Dict[str, Any]] = listing.json["content"]["projects"]
        assert projects[0]["id"] == workspace.identifier

    @pytest.mark.parametrize(
        "arguments",
        [
            ("--global-id", "--refresh"),
            ("--refresh", "extra"),
        ],
    )
    def test_refresh_rejects_invalid_arguments(
        self,
        cli_runner: InfobimCliProcessRunner,
        arguments: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("project", *arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
