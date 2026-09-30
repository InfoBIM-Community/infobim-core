from typing import Any, Dict, List
from pathlib import Path

import pytest

from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
    main as prepare_metadata,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
    main as prepare_storage_index,
)
from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.storage.adapter.repository import LoadedStorageGraph

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimProjectDeleteCommand:
    def test_delete_removes_the_project_from_the_storage_index(
        self, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        runner: InfobimCliProcessRunner = InfobimCliProcessRunner(tmp_path)
        before_listing: CliInvocationResult = runner.run("project", "--list")
        assert before_listing.exit_code == 0, before_listing.stdout
        assert len(before_listing.json["content"]["projects"]) == 1

        result: CliInvocationResult = runner.run(
            "project", "--delete", workspace.identifier
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        after_listing: CliInvocationResult = runner.run("project", "--list")
        assert after_listing.exit_code == 0, after_listing.stdout
        assert after_listing.json["content"]["projects"] == []

    def test_delete_preserves_project_files_on_disk(
        self, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        runner: InfobimCliProcessRunner = InfobimCliProcessRunner(tmp_path)
        marker: Path = workspace.project / "keep-me.txt"
        marker.write_text("preserved", encoding="utf-8")

        result: CliInvocationResult = runner.run(
            "project", "--delete", workspace.identifier
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert workspace.project.is_dir()
        assert marker.read_text(encoding="utf-8") == "preserved"

    def test_delete_refuses_a_plain_container_that_is_not_a_project(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        cli_runner.run("init")
        plain_container: Path = tmp_path / "plain"
        plain_container.mkdir()
        prepare_metadata(container_path=str(plain_container), root_path=str(tmp_path))
        prepare_storage_index(container_path=str(plain_container), root_path=str(tmp_path))
        storage = LoadedStorageGraph(StorageFileLocator.resolve(str(tmp_path)))
        entries: List[Dict[str, Any]] = storage.storage_graph.list_containers()
        assert len(entries) == 1
        container_id: Any = entries[0]["id"]
        assert isinstance(container_id, str)

        result: CliInvocationResult = cli_runner.run(
            "project", "--delete", container_id
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"

    def test_delete_rejects_missing_identifier(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run("project", "--delete")

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
