import os
import json
import shutil
from typing import Any, Dict, List, Set
from pathlib import Path

import pytest
import ifcopenshell

from test.e2e.project_workspace import ProjectE2eWorkspace
from test.e2e.cli_process_runner import (
    CliInvocationResult,
    InfobimCliProcessRunner,
    InfobimTerminalProcessRunner,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as prepare_manifest,
)


class IfcInspectTerminalRunner(InfobimTerminalProcessRunner):
    _TIMEOUT_SECONDS: int = 180


class TestInfobimProjectInteractiveInspectIfcCommand:
    def test_interactive_inspect_opens_embedded_revit_ifc_in_3d_viewer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fixture: Path = Path(__file__).parent / "assets" / "Ifc4_Revit_ARC.ifc"
        original_bytes: bytes = fixture.read_bytes()
        workspace: ProjectE2eWorkspace = ProjectE2eWorkspace.create(
            tmp_path, name="Mi Casa, Su Casa"
        )
        model_path: Path = workspace.project / fixture.name
        shutil.copyfile(fixture, model_path)
        assert prepare_manifest(
            container_path=str(workspace.project), root_path=str(workspace.root)
        ) == 0
        assert fixture.name in workspace.manifest_files()
        model: ifcopenshell.file = ifcopenshell.open(str(model_path))
        assert model.schema_identifier == "IFC4"
        product: ifcopenshell.entity_instance
        product_ids: Set[str] = {
            product.GlobalId for product in model.by_type("IfcProduct")
        }

        inspected: CliInvocationResult = InfobimCliProcessRunner(workspace.project).run(
            "project", "--global-id", workspace.identifier, "--inspect"
        )
        assert inspected.exit_code == 0, inspected.stdout + inspected.stderr
        tree: Dict[str, Any] = inspected.json["content"]["tree"]
        cursor_offset: int = self._model_cursor_offset(tree, fixture.name)

        bootstrap: Path = tmp_path / "qt-viewer-probe"
        bootstrap.mkdir()
        shutil.copyfile(
            Path(__file__).parents[1] / "ifc_viewer_window_probe.py",
            bootstrap / "sitecustomize.py",
        )
        evidence_path: Path = tmp_path / "ifc-viewer-frame.json"
        pythonpath: List[str] = [str(bootstrap)]
        if "PYTHONPATH" in os.environ:
            pythonpath.append(os.environ["PYTHONPATH"])
        monkeypatch.setenv("PYTHONPATH", os.pathsep.join(pythonpath))
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        monkeypatch.setenv("INFOBIM_E2E_VIEWER_EVIDENCE", str(evidence_path))

        result: CliInvocationResult = IfcInspectTerminalRunner(workspace.project).run(
            "project",
            "--global-id",
            workspace.identifier,
            "--inspect",
            "-i",
            ready_marker="InfoBIM Project",
            keys="fe\x1b[H" + ("\x1b[B" * cursor_offset) + "oq",
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert "Traceback" not in result.stdout, result.stdout
        assert evidence_path.is_file(), result.stdout
        evidence: Dict[str, Any] = json.loads(evidence_path.read_text(encoding="utf-8"))
        assert evidence["title"] == "InfoBIM 3D Viewer"
        assert evidence["visible"] is True
        rendered_ids: Set[str] = set(evidence["global_ids"])
        assert rendered_ids
        assert rendered_ids <= product_ids

        events: List[Path] = list(
            workspace.root.rglob("__file_opening_strategy_found__.json")
        )
        assert len(events) == 1, events
        event: Dict[str, Any] = json.loads(events[0].read_text(encoding="utf-8"))
        capability_id: str = "org.infobim._3d.plugin.capability.loader.ifc_open_file"
        assert event["state"] == "file_opening_strategy_found"
        assert event["strategies"] == [capability_id]
        assert event["results"][capability_id] == {
            "handled": True,
            "handler": "ifc_quick3d",
            "message": "Opened the IFC file in the InfoBIM 3D viewer.",
            "error": None,
        }
        assert model_path.read_bytes() == original_bytes
        assert fixture.read_bytes() == original_bytes

    @staticmethod
    def _model_cursor_offset(tree: Dict[str, Any], filename: str) -> int:
        pending: List[Dict[str, Any]] = [tree]
        index: int = 0
        while pending:
            node: Dict[str, Any] = pending.pop()
            if node["kind"] == "model" and node["name"] == filename:
                assert node["path"] == filename
                return index
            if "children" in node:
                pending.extend(reversed(node["children"]))
            index += 1
        raise AssertionError(f"The project tree does not contain the IFC model {filename}.")
