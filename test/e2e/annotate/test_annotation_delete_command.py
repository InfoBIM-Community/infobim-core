"""Installed CLI routing for `infobim annotate --guid <id> --delete`."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimAnnotationDeleteCommand:

    def test_delete_without_annotations_fails_with_lookup_error(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--guid",
            "nonexistent",
            "--delete",
        )

        assert result.exit_code != 0
        assert "Run Exception" in result.stdout
        assert "keeps no annotations" in result.stdout
        assert workspace.snapshot() == before

    def test_delete_removes_an_existing_annotation(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        created: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--title",
            "To be deleted",
        )
        assert created.exit_code == 0
        guid: str = created.json["content"]["global_id"]

        deleted: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--guid",
            guid,
            "--delete",
        )

        assert deleted.exit_code == 0, deleted.stdout + deleted.stderr
        assert deleted.json["title"] == "Annotation Deleted"
        assert deleted.json["content"]["global_id"] == guid

    def test_delete_unknown_guid_fails_after_annotations_exist(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        created: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--title",
            "Existing",
        )
        assert created.exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--guid",
            "does-not-exist",
            "--delete",
        )

        assert result.exit_code != 0
        assert "Run Exception" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--guid", "abc"),
            ("--delete",),
            ("--guid", "--delete"),
            ("--guid", "abc", "--delete", "extra"),
            ("--guid", "abc", "--guid", "def", "--delete"),
        ],
    )
    def test_invalid_delete_route_does_not_remove_annotations(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("annotate", *args)

        assert result.exit_code != 0, result.stdout
        assert "Annotation Deleted" not in result.stdout
        assert workspace.snapshot() == before
