import json
from typing import Any, Dict, List, Set
from pathlib import Path

from test.e2e.project_workspace import ProjectE2eWorkspace
from test.e2e.cli_process_runner import CliInvocationResult, InfobimCliProcessRunner


class TestInfobimProjectHealthCommand:

    def test_health_reports_a_healthy_project_without_modifying_it(
        self,
        cli_runner: InfobimCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()
        storage: Path = workspace.root / ".__ontobdc__" / "storage.ttl"
        storage_before: bytes = storage.read_bytes()
        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--health"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Project Health"
        assert result.json["severity"] == "SUCCESS"
        assert result.json["content"]["healthy"] is True
        checks: List[Dict[str, Any]] = result.json["content"]["checks"]
        check_ids: Set[str] = {check["identifier"] for check in checks}
        assert "project_dataset_ready" in check_ids
        assert "ifc_project_ready" in check_ids
        assert "ifc_project_schema_ready" in check_ids
        assert all(check["passed"] is True for check in checks)
        assert workspace.snapshot() == before
        assert storage.read_bytes() == storage_before

    def test_health_infers_project_from_cwd_without_global_id(
        self,
        tmp_path: Path,
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()
        storage: Path = workspace.root / ".__ontobdc__" / "storage.ttl"
        storage_before: bytes = storage.read_bytes()

        result: CliInvocationResult = workspace.runner().run("project", "--health")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Project Health"
        assert result.json["severity"] == "SUCCESS"
        assert result.json["content"]["healthy"] is True
        checks: List[Dict[str, Any]] = result.json["content"]["checks"]
        check_ids: Set[str] = {check["identifier"] for check in checks}
        assert "project_dataset_ready" in check_ids
        assert "ifc_project_ready" in check_ids
        assert "ifc_project_schema_ready" in check_ids
        assert all(check["passed"] is True for check in checks)
        assert workspace.snapshot() == before
        assert storage.read_bytes() == storage_before

    def test_health_reports_project_dataset_csv_drift_without_repairing_it(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        initial: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--health"
        )
        assert initial.exit_code == 0, initial.stdout + initial.stderr
        assert initial.json["severity"] == "SUCCESS"
        assert initial.json["content"]["healthy"] is True

        stray: Path = workspace.project / ".__infobim__" / "stray.csv"
        stray.write_text("value\n42\n", encoding="utf-8")
        before: Dict[str, bytes] = workspace.snapshot()
        storage: Path = workspace.root / ".__ontobdc__" / "storage.ttl"
        storage_before: bytes = storage.read_bytes()

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--health"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["severity"] == "ERROR"
        assert result.json["content"]["healthy"] is False
        checks: Dict[str, bool] = {
            check["identifier"]: check["passed"]
            for check in result.json["content"]["checks"]
            if check["scope"] == ".__infobim__"
        }
        assert checks["dataset_healthy"] is False
        assert workspace.snapshot() == before
        assert storage.read_bytes() == storage_before

    def test_health_ignores_project_dataset_txt_without_modifying_it(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        ignored: Path = workspace.project / ".__infobim__" / "stray.txt"
        ignored.write_text("stray content", encoding="utf-8")
        before: Dict[str, bytes] = workspace.snapshot()
        storage: Path = workspace.root / ".__ontobdc__" / "storage.ttl"
        storage_before: bytes = storage.read_bytes()

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--health"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Project Health"
        assert result.json["severity"] == "SUCCESS"
        assert result.json["content"]["healthy"] is True
        checks: List[Dict[str, Any]] = result.json["content"]["checks"]
        assert all(check["passed"] is True for check in checks)
        assert workspace.snapshot() == before
        assert storage.read_bytes() == storage_before

    def test_health_ignores_unsupported_stray_file_in_project_dataset(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        dataset: Path = workspace.project / ".__infobim__"
        stray: Path = dataset / "stray.txt"
        stray.write_text("stray content", encoding="utf-8")
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--health"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["severity"] == "SUCCESS", result.stdout
        datapackage: Dict[str, Any] = json.loads(
            (dataset / ".__ontobdc__" / "datapackage.json").read_text(encoding="utf-8")
        )
        resource_paths: List[Any] = [
            resource["path"] for resource in datapackage["resources"]
        ]
        assert stray.name not in resource_paths
        assert workspace.snapshot() == before


    def test_health_requires_a_project(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", "urn:uuid:00000000-0000-0000-0000-000000000000", "--health"
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"

    def test_health_rejects_a_selector_without_a_value(
        self, cli_runner: InfobimCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", "--health"
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
