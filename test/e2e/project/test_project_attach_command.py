from typing import Any, Dict, List, Tuple
from pathlib import Path

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner
from test.e2e.project_workspace import ProjectE2eWorkspace


class TestInfobimProjectAttachCommand:
    @pytest.mark.parametrize("selector", ["cwd", "--project-path", "--project"])
    def test_attach_imports_a_moved_project_preserving_identity_and_user_files(
        self,
        tmp_path: Path,
        selector: str,
    ) -> None:
        source_root: Path = tmp_path / "origin"
        source_root.mkdir()
        source: ProjectE2eWorkspace = ProjectE2eWorkspace.create(source_root)
        (source.project / "measurements.csv").write_text(
            "value\n42\n", encoding="utf-8"
        )
        target_root: Path = tmp_path / "destination"
        target_root.mkdir()
        target_runner: InfobimCliProcessRunner = InfobimCliProcessRunner(target_root)
        assert target_runner.run("init").exit_code == 0
        imported: Path = target_root / "imported"
        source.project.rename(imported)
        runner: InfobimCliProcessRunner
        arguments: Tuple[str, ...]
        if selector == "cwd":
            runner = InfobimCliProcessRunner(imported)
            arguments = ("project", "--attach")
        else:
            runner = target_runner
            arguments = ("project", selector, str(imported), "--attach")

        result: CliInvocationResult = runner.run(*arguments)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project Attached"
        assert (
            Path(result.json["content"]["project_path"]).resolve()
            == imported.resolve()
        )
        listing: CliInvocationResult = target_runner.run("project", "--list")
        assert listing.exit_code == 0, listing.stdout
        entries: List[Dict[str, Any]] = listing.json["content"]["projects"]
        assert len(entries) == 1
        assert entries[0]["id"] == source.identifier
        assert Path(entries[0]["location"]).resolve() == imported.resolve()
        assert (imported / "measurements.csv").read_bytes() == b"value\n42\n"

    def test_attach_rejects_a_nonexistent_directory(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        assert cli_runner.run("init").exit_code == 0
        missing: Path = tmp_path / "missing"

        result: CliInvocationResult = cli_runner.run(
            "project", "--project-path", str(missing), "--attach"
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
        assert not missing.exists()

    @pytest.mark.parametrize(
        "arguments",
        [
            ("--attach", "--attach"),
            ("--project-path", "--attach"),
            ("--project-path", "", "--attach"),
        ],
    )
    def test_attach_rejects_duplicate_flags_and_missing_paths(
        self,
        cli_runner: InfobimCliProcessRunner,
        arguments: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("project", *arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
