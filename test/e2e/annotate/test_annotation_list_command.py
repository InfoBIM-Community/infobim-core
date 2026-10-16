"""Installed CLI routing for `infobim annotate --list`."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimAnnotationListCommand:

    def test_list_returns_empty_groups_for_a_fresh_project(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "annotate", "--global-id", workspace.selector("id"), "--list"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Annotations"
        groups: List[Dict[str, Any]] = result.json["content"]["groups"]
        assert isinstance(groups, list)
        assert len(groups) >= 1
        assert all(group["annotations"] == [] for group in groups)
        assert workspace.snapshot() == before

    def test_list_resolves_project_from_current_directory(
        self,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = workspace.runner().run("annotate", "--list")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Annotations"

    @pytest.mark.parametrize(
        "args",
        [
            ("--list", "extra"),
            ("--list", "--global-id"),
            ("--global-id", "id", "--list", "extra"),
        ],
    )
    def test_invalid_list_route_fails_without_listing_annotations(
        self,
        cli_runner: InfobimCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("annotate", *args)

        assert result.exit_code != 0, result.stdout
        assert "Annotations" not in result.stdout
