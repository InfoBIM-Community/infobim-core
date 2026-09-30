import shutil
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import ifcopenshell
import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from test.e2e.cli_process_runner import (
    _BaseCliProcessRunner,
    CliInvocationResult,
    InfobimCliProcessRunner,
)
from test.e2e.project_workspace import ProjectE2eWorkspace


_ASSETS_DIR: Path = Path(__file__).parent / "assets"
_IFC_FILENAME: str = "Ifc4_Revit_ARC.ifc"


class _LongTimeoutInfobimCliProcessRunner(_BaseCliProcessRunner):
    _TIMEOUT_SECONDS: int = 600
    _EXECUTABLE_NAME: str = "infobim"


class TestInfobimProjectRefreshCommand:

    def test_refresh_accepts_embedded_revit_ifc4_in_an_ifc43_project(
        self, cli_runner: InfobimCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        descriptor: Path = (
            workspace.project / ".__infobim__" / "payload" / "triple" / "ifc_project.ttl"
        )
        project_graph: Graph = Graph().parse(descriptor, format="turtle")
        project_type: URIRef = URIRef(
            "https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#IfcProject"
        )
        assert (None, RDF.type, project_type) in project_graph

        fixture: Path = (
            Path(__file__).resolve().parents[1] / "fixtures" / "ifc" / "Ifc4_Revit_ARC.ifc"
        )
        fixture_bytes: bytes = fixture.read_bytes()
        model_path: Path = workspace.project / fixture.name
        shutil.copyfile(fixture, model_path)
        original_model: ifcopenshell.file = ifcopenshell.open(str(model_path))
        assert original_model.schema_identifier == "IFC4"
        original_project_id: str = original_model.by_type("IfcProject")[0].GlobalId
        product: ifcopenshell.entity_instance
        original_product_ids: Set[str] = {
            product.GlobalId for product in original_model.by_type("IfcProduct")
        }
        assert model_path.name not in workspace.manifest_files()

        result: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project Refreshed"
        assert result.json["content"]["current_state"] == "__project_ready_to_render__"
        assert model_path.name in workspace.manifest_files()
        refreshed_model: ifcopenshell.file = ifcopenshell.open(str(model_path))
        assert refreshed_model.schema_identifier == "IFC4"
        assert refreshed_model.by_type("IfcProject")[0].GlobalId == original_project_id
        assert {
            product.GlobalId for product in refreshed_model.by_type("IfcProduct")
        } == original_product_ids

        health: CliInvocationResult = cli_runner.run(
            "project", "--global-id", workspace.selector("id"), "--health"
        )
        assert health.exit_code == 0, health.stdout + health.stderr
        assert health.json["severity"] == "SUCCESS", health.stdout
        assert health.json["content"]["healthy"] is True
        assert fixture.read_bytes() == fixture_bytes

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

    def test_refresh_with_embedded_ifc4_revit_arc_processes_file_and_preserves_content(
        self,
        tmp_path: Path,
    ) -> None:
        ifc_source: Path = _ASSETS_DIR / _IFC_FILENAME
        assert ifc_source.is_file(), f"Embedded IFC fixture missing at {ifc_source}"
        expected_bytes: bytes = ifc_source.read_bytes()
        assert len(expected_bytes) > 0, "Embedded IFC fixture is empty"

        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        ifc_destination: Path = workspace.project / _IFC_FILENAME
        shutil.copyfile(ifc_source, ifc_destination)
        assert ifc_destination.read_bytes() == expected_bytes
        assert _IFC_FILENAME not in workspace.manifest_files()

        long_runner: _LongTimeoutInfobimCliProcessRunner = (
            _LongTimeoutInfobimCliProcessRunner(isolated_project_root=workspace.root)
        )
        result: CliInvocationResult = long_runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "InfoBIM Project Refreshed"
        content: Dict[str, Any] = result.json["content"]
        assert "container_visited_states" in content
        assert "project_visited_states" in content
        assert isinstance(content["container_visited_states"], list)
        assert isinstance(content["project_visited_states"], list)
        assert _IFC_FILENAME in workspace.manifest_files()
        assert ifc_destination.read_bytes() == expected_bytes

    def test_refresh_with_embedded_ifc4_revit_arc_is_idempotent(
        self,
        tmp_path: Path,
    ) -> None:
        ifc_source: Path = _ASSETS_DIR / _IFC_FILENAME
        assert ifc_source.is_file(), f"Embedded IFC fixture missing at {ifc_source}"
        expected_bytes: bytes = ifc_source.read_bytes()

        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(tmp_path)
        ifc_destination: Path = workspace.project / _IFC_FILENAME
        shutil.copyfile(ifc_source, ifc_destination)

        long_runner: _LongTimeoutInfobimCliProcessRunner = (
            _LongTimeoutInfobimCliProcessRunner(isolated_project_root=workspace.root)
        )
        first: CliInvocationResult = long_runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )
        second: CliInvocationResult = long_runner.run(
            "project", "--global-id", workspace.selector("id"), "--refresh"
        )

        assert first.exit_code == 0, first.stdout + first.stderr
        assert second.exit_code == 0, second.stdout + second.stderr
        assert _IFC_FILENAME in workspace.manifest_files()
        assert ifc_destination.read_bytes() == expected_bytes
        listing: CliInvocationResult = InfobimCliProcessRunner(workspace.root).run(
            "project", "--list"
        )
        assert listing.exit_code == 0, listing.stdout
        projects: List[Dict[str, Any]] = listing.json["content"]["projects"]
        assert [entry["id"] for entry in projects] == [workspace.identifier]
