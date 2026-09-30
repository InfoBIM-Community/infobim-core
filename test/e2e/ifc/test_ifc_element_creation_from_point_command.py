import os
import json
import shutil
from typing import Any, Dict, List, Set, Tuple
from pathlib import Path

import pytest

from ontobdc.shared.adapter.slug import TitleSlug
from ontobdc.storage.adapter.crate import ContainerRoCrate
from ontobdc.storage.adapter.open_file_metadata import OpenFileMetadataEvent
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)

from test.e2e.project_workspace import ProjectE2eWorkspace
from test.e2e.cli_process_runner import CliInvocationResult
from infobim.project.adapter.contract import ProjectGuard
from test.e2e.ifc.point_capture_support import (
    FIXTURE_DXF,
    CaptureScript,
    ProjectIfcModel,
    IfcPointCommandRunner,
    PointCaptureEnvironment,
)

TERM: str = "Sapata"
EXPECTED_IFC_CLASS: str = "IfcFooting"
EXPECTED_PREDEFINED_TYPE: str = "NOTDEFINED"
P1: Tuple[float, float] = (10.0, 10.0)
P2: Tuple[float, float] = (40.0, 10.0)
P3: Tuple[float, float] = (40.0, 30.0)
P3_REPLACEMENT: Tuple[float, float] = (20.0, 40.0)
FINISH: Tuple[float, float] = (30.0, 20.0)
CLICK_TOLERANCE: float = 0.5
FIXTURE_IFC_DIRECTORY: Path = FIXTURE_DXF.parent.parent / "ifc"


class TestIfcElementCreationFromPointCommand:
    """
    ``infobim ifc --global-id <id> --term <term> --point <drawing>``.

    Every test runs the real CLI in a subprocess: the term goes through the
    dictionary states, the drawing is opened in the 2D viewer, the probe
    picks points on that window, and the IFC model of the project is read
    back from disk.
    """

    def test_dxf_creates_one_ifc_element_per_kept_point(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = self._workspace(tmp_path)
        global_id: str = self._global_id(workspace.project)
        assert ProjectIfcModel.models(workspace.project) == []
        capture: PointCaptureEnvironment = PointCaptureEnvironment.install(
            monkeypatch,
            tmp_path,
            [
                CaptureScript.click(*P1),
                CaptureScript.click(*P2),
                CaptureScript.click(*P3),
                CaptureScript.key("backspace"),
                CaptureScript.click(*P3_REPLACEMENT),
                CaptureScript.key("delete"),
                CaptureScript.double_click(*FINISH),
            ],
        )

        result: CliInvocationResult = IfcPointCommandRunner(workspace.root).run(
            "ifc",
            "--global-id",
            global_id,
            "--term",
            TERM,
            "--point",
            str(FIXTURE_DXF),
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        evidence: Dict[str, Any] = capture.evidence()
        assert evidence["error"] is None, evidence
        assert evidence["dialogs_created"] == 1
        marker_counts: List[int] = [len(step["markers"]) for step in evidence["steps"]]
        assert marker_counts[:6] == [1, 2, 3, 2, 3, 2]
        kept_markers: List[Dict[str, Any]] = evidence["steps"][5]["markers"]
        assert {marker["color"] for marker in kept_markers} == {"#00ffff"}
        assert all(len(marker["labels"]) == 1 for marker in kept_markers)

        content: Dict[str, Any] = result.json["content"]
        assert content["global_id"] == global_id
        assert content["term"] == TERM
        assert content["drawing"] == str(FIXTURE_DXF)
        assert content["created_count"] == 3
        created: List[Dict[str, Any]] = content["ifc_elements"]
        assert [(element["x"], element["y"]) for element in created[:2]] == [
            (marker["x"], marker["y"])
            for marker in sorted(kept_markers, key=lambda marker: marker["x"])
        ]
        self._assert_near(created[0], P1)
        self._assert_near(created[1], P2)
        self._assert_near(created[2], FINISH)

        models: List[Path] = ProjectIfcModel.models(workspace.project)
        assert [str(model) for model in models] == [content["ifc_model_path"]]
        assert models[0] == workspace.project / f"{TitleSlug.of(global_id)}.ifc"
        assert models[0].name in ContainerRoCrate.file_paths(workspace.project)
        elements: Dict[str, Any] = ProjectIfcModel.elements(models[0])
        assert len(elements) == 3
        assert set(elements) == {element["global_id"] for element in created}
        element_data: Dict[str, Any]
        for element_data in created:
            element: Any = elements[element_data["global_id"]]
            assert element.is_a() == EXPECTED_IFC_CLASS
            assert element_data["ifc_class"] == EXPECTED_IFC_CLASS
            assert element.PredefinedType == EXPECTED_PREDEFINED_TYPE
            assert element.Representation is not None
            location: Tuple[float, float, float] = ProjectIfcModel.block_location(element)
            assert location == (element_data["x"], element_data["y"], 0.0)
        locations: Set[Tuple[float, float]] = {
            ProjectIfcModel.block_location(element)[:2] for element in elements.values()
        }
        removed: Tuple[float, float]
        for removed in (P3, P3_REPLACEMENT):
            assert all(
                self._distance(location, removed) > CLICK_TOLERANCE
                for location in locations
            )

    def test_global_id_selects_the_project_independently_of_the_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        selected: ProjectE2eWorkspace = self._workspace(tmp_path, "selected")
        other: ProjectE2eWorkspace = self._workspace(tmp_path, "other")
        other_before: Dict[str, bytes] = other.snapshot()
        PointCaptureEnvironment.install(
            monkeypatch,
            tmp_path,
            [CaptureScript.double_click(*P1)],
        )

        result: CliInvocationResult = IfcPointCommandRunner(other.project).run(
            "ifc",
            "--global-id",
            self._global_id(selected.project),
            "--term",
            TERM,
            "--point",
            str(FIXTURE_DXF),
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        created: List[Dict[str, Any]] = result.json["content"]["ifc_elements"]
        models: List[Path] = ProjectIfcModel.models(selected.project)
        assert len(models) == 1
        assert set(ProjectIfcModel.elements(models[0])) == {created[0]["global_id"]}
        assert ProjectIfcModel.models(other.project) == []
        assert other.snapshot() == other_before

    def test_global_id_is_optional_inside_the_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = self._workspace(tmp_path)
        PointCaptureEnvironment.install(
            monkeypatch,
            tmp_path,
            [CaptureScript.double_click(*P1)],
        )

        drawing: str = os.path.relpath(FIXTURE_DXF, workspace.project)

        result: CliInvocationResult = IfcPointCommandRunner(workspace.project).run(
            "ifc",
            "--term",
            TERM,
            "--point",
            drawing,
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["content"]["drawing"] == drawing
        created: List[Dict[str, Any]] = result.json["content"]["ifc_elements"]
        assert len(created) == 1
        self._assert_near(created[0], P1)
        elements: Dict[str, Any] = ProjectIfcModel.elements(
            ProjectIfcModel.models(workspace.project)[0]
        )
        assert set(elements) == {created[0]["global_id"]}

    def test_project_with_other_models_gets_its_own_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = self._workspace(tmp_path)
        received: List[Path] = []
        fixture: Path
        for fixture in (
            FIXTURE_IFC_DIRECTORY / "BasicHouse.ifc",
            FIXTURE_IFC_DIRECTORY / "Ifc4_Revit_ARC.ifc",
        ):
            target: Path = workspace.project / fixture.name
            shutil.copyfile(fixture, target)
            received.append(target)
        assert hotfix_container_manifest_synced(
            container_path=str(workspace.project),
            root_path=str(workspace.root),
        ) == 0
        received_before: Dict[str, bytes] = {
            str(path): path.read_bytes() for path in received
        }
        PointCaptureEnvironment.install(
            monkeypatch,
            tmp_path,
            [CaptureScript.double_click(*P1)],
        )

        result: CliInvocationResult = IfcPointCommandRunner(workspace.project).run(
            "ifc",
            "--term",
            TERM,
            "--point",
            str(FIXTURE_DXF),
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        own_model: Path = (
            workspace.project
            / f"{TitleSlug.of(self._global_id(workspace.project))}.ifc"
        )
        content: Dict[str, Any] = result.json["content"]
        assert content["ifc_model_path"] == str(own_model)
        assert own_model.name in ContainerRoCrate.file_paths(workspace.project)
        assert set(ProjectIfcModel.elements(own_model)) == {
            content["ifc_elements"][0]["global_id"]
        }
        assert {
            str(path): path.read_bytes() for path in received
        } == received_before

    def test_flags_are_accepted_in_any_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = self._workspace(tmp_path)
        PointCaptureEnvironment.install(
            monkeypatch,
            tmp_path,
            [CaptureScript.double_click(*P2)],
        )

        result: CliInvocationResult = IfcPointCommandRunner(workspace.root).run(
            "ifc",
            "--point",
            str(FIXTURE_DXF),
            "--global-id",
            self._global_id(workspace.project),
            "--term",
            TERM,
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        created: List[Dict[str, Any]] = result.json["content"]["ifc_elements"]
        assert len(created) == 1
        self._assert_near(created[0], P2)
        elements: Dict[str, Any] = ProjectIfcModel.elements(
            ProjectIfcModel.models(workspace.project)[0]
        )
        assert [element.is_a() for element in elements.values()] == [EXPECTED_IFC_CLASS]

    def test_dwg_is_converted_before_the_points_are_captured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = self._workspace(tmp_path)
        drawing: Path = tmp_path / "floor_plan.dwg"
        drawing.write_bytes(b"AC1032 end-to-end DWG placeholder")
        capture: PointCaptureEnvironment = PointCaptureEnvironment.install(
            monkeypatch,
            tmp_path,
            [CaptureScript.double_click(*P1)],
        )
        capture.install_fake_oda_converter(monkeypatch, tmp_path, FIXTURE_DXF)

        result: CliInvocationResult = IfcPointCommandRunner(workspace.root).run(
            "ifc",
            "--global-id",
            self._global_id(workspace.project),
            "--term",
            TERM,
            "--point",
            str(drawing),
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        conversion: Dict[str, Any] = json.loads(
            capture.oda_log_path.read_text(encoding="utf-8")
        )
        assert conversion["input"].endswith(".dwg")
        metadata: Dict[str, Any] = json.loads(
            OpenFileMetadataEvent.path(workspace.root).read_text(encoding="utf-8")
        )
        converted: Path = Path(metadata["resolved_path"])
        assert converted.suffix == ".dxf"
        assert converted.is_relative_to(workspace.project)
        assert converted.read_bytes() == FIXTURE_DXF.read_bytes()
        assert metadata["mime"] == "image/vnd.dxf"
        assert capture.evidence()["dialogs_created"] == 1
        content: Dict[str, Any] = result.json["content"]
        assert content["drawing"] == str(drawing)
        assert content["created_count"] == 1
        self._assert_near(content["ifc_elements"][0], P1)
        elements: Dict[str, Any] = ProjectIfcModel.elements(
            ProjectIfcModel.models(workspace.project)[0]
        )
        assert set(elements) == {content["ifc_elements"][0]["global_id"]}

    def test_unknown_global_id_fails_without_touching_projects(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = self._workspace(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()
        PointCaptureEnvironment.install(
            monkeypatch,
            tmp_path,
            [CaptureScript.double_click(*P1)],
        )

        result: CliInvocationResult = IfcPointCommandRunner(workspace.root).run(
            "ifc",
            "--global-id",
            "0000000000000000000000",
            "--term",
            TERM,
            "--point",
            str(FIXTURE_DXF),
        )

        assert result.exit_code == 1, result.stdout
        assert "Invalid command arguments" in result.json["content"]["error"]
        assert workspace.snapshot() == before

    def test_unsupported_drawing_fails_without_creating_elements(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = self._workspace(tmp_path)
        drawing: Path = tmp_path / "notes.txt"
        drawing.write_text("not a drawing\n", encoding="utf-8")
        capture: PointCaptureEnvironment = PointCaptureEnvironment.install(
            monkeypatch,
            tmp_path,
            [CaptureScript.double_click(*P1)],
        )

        result: CliInvocationResult = IfcPointCommandRunner(workspace.root).run(
            "ifc",
            "--global-id",
            self._global_id(workspace.project),
            "--term",
            TERM,
            "--point",
            str(drawing),
        )

        assert result.exit_code == 1, result.stdout
        assert "text/plain" in result.json["content"]["error"]
        assert not capture.evidence_path.exists()
        self._assert_own_model_without_elements(workspace.project)

    def test_closing_the_viewer_without_double_click_creates_no_element(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = self._workspace(tmp_path)
        capture: PointCaptureEnvironment = PointCaptureEnvironment.install(
            monkeypatch,
            tmp_path,
            [CaptureScript.click(*P1), CaptureScript.close()],
        )

        result: CliInvocationResult = IfcPointCommandRunner(workspace.root).run(
            "ifc",
            "--global-id",
            self._global_id(workspace.project),
            "--term",
            TERM,
            "--point",
            str(FIXTURE_DXF),
        )

        assert result.exit_code == 1, result.stdout
        assert "double click" in result.json["content"]["error"]
        assert capture.evidence()["steps"][0]["markers"]
        self._assert_own_model_without_elements(workspace.project)

    @staticmethod
    def _workspace(
        tmp_path: Path, name: str = "project-under-test"
    ) -> ProjectE2eWorkspace:
        root: Path = tmp_path / "root"
        root.mkdir(exist_ok=True)
        return ProjectE2eWorkspace.create(root, name=name)

    @staticmethod
    def _global_id(project: Path) -> str:
        global_id: Any = ProjectGuard.ifc_project_global_id(project)
        assert isinstance(global_id, str) and global_id
        return global_id

    @classmethod
    def _assert_own_model_without_elements(cls, project: Path) -> None:
        """
        The project's own model is created before anything else runs, so a
        run that fails later leaves it in place, carrying no element.
        """
        own_model: Path = project / f"{TitleSlug.of(cls._global_id(project))}.ifc"
        assert ProjectIfcModel.models(project) == [own_model]
        assert ProjectIfcModel.elements(own_model) == {}

    @classmethod
    def _assert_near(cls, element: Dict[str, Any], target: Tuple[float, float]) -> None:
        assert cls._distance((element["x"], element["y"]), target) <= CLICK_TOLERANCE
        assert element["z"] == 0.0

    @staticmethod
    def _distance(first: Tuple[float, float], second: Tuple[float, float]) -> float:
        return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5
