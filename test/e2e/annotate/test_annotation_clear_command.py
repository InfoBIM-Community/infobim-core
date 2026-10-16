"""Installed CLI routing for `infobim annotate --guid <id> --clear <field>`."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimAnnotationClearCommand:

    def test_clear_without_annotations_fails_with_lookup_error(
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
            "--clear",
            "text",
        )

        assert result.exit_code != 0
        assert "Run Exception" in result.stdout
        assert "keeps no annotations" in result.stdout
        assert workspace.snapshot() == before

    def test_clear_empties_a_field_of_an_existing_annotation(
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
            "With body",
            "--text",
            "Body to clear",
            "--author",
            "Elias",
        )
        assert created.exit_code == 0
        guid: str = created.json["content"]["global_id"]

        cleared: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--guid",
            guid,
            "--clear",
            "text",
        )

        assert cleared.exit_code == 0, cleared.stdout + cleared.stderr
        assert cleared.json["title"] == "Annotation Cleared"
        assert cleared.json["content"]["global_id"] == guid
        assert "text" in cleared.json["content"]["cleared"]

    @pytest.mark.parametrize("field", ["text", "author", "related"])
    def test_clear_accepts_every_clearable_field(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        field: str,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        created: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--title",
            "Target",
        )
        assert created.exit_code == 0
        guid: str = created.json["content"]["global_id"]

        result: CliInvocationResult = cli_runner.run(
            "annotate",
            "--global-id",
            workspace.selector("id"),
            "--guid",
            guid,
            "--clear",
            field,
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Annotation Cleared"

    @pytest.mark.parametrize(
        "args",
        [
            ("--guid", "abc"),
            ("--clear", "text"),
            ("--guid", "abc", "--clear"),
            ("--guid", "abc", "--clear", "not-a-field"),
            ("--guid", "abc", "--clear", "title"),
            ("--guid", "abc", "--clear", "text", "extra"),
        ],
    )
    def test_invalid_clear_route_does_not_modify_annotations(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("annotate", *args)

        assert result.exit_code != 0, result.stdout
        assert "Annotation Cleared" not in result.stdout
        assert workspace.snapshot() == before
