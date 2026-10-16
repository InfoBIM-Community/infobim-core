"""Installed CLI routing for `infobim annotate --guid <id> --title <new>` (update)."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimAnnotationUpdateCommand:

    def test_update_without_annotations_fails_with_lookup_error(
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
            "--title",
            "New",
        )

        assert result.exit_code != 0
        assert "Run Exception" in result.stdout
        assert "keeps no annotations" in result.stdout
        assert workspace.snapshot() == before

    def test_update_changes_the_title_of_an_existing_annotation(
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
            "Original",
        )
        assert created.exit_code == 0
        guid: str = created.json["content"]["global_id"]

        updated: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--guid",
            guid,
            "--title",
            "Updated",
        )

        assert updated.exit_code == 0, updated.stdout + updated.stderr
        assert updated.json["title"] == "Annotation Updated"
        assert updated.json["content"]["global_id"] == guid
        assert updated.json["content"]["title"] == "Updated"

    def test_update_accepts_multiple_change_flags(
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
            "Original",
        )
        assert created.exit_code == 0
        guid: str = created.json["content"]["global_id"]

        result: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--guid",
            guid,
            "--title",
            "Changed",
            "--text",
            "New body",
            "--author",
            "Elias",
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Annotation Updated"
        assert "title" in result.json["content"]["changed"]
        assert "text" in result.json["content"]["changed"]
        assert "author" in result.json["content"]["changed"]

    @pytest.mark.parametrize(
        "args",
        [
            ("--guid", "abc"),
            ("--title", "New"),
            ("--guid", "abc", "--title"),
            ("--title", "New", "--guid"),
            ("--guid", "abc", "--title", "New", "extra"),
            ("--guid", "abc", "--guid", "def", "--title", "New"),
        ],
    )
    def test_invalid_update_route_does_not_modify_annotations(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("annotate", *args)

        assert result.exit_code != 0, result.stdout
        assert "Annotation Updated" not in result.stdout
        assert workspace.snapshot() == before
