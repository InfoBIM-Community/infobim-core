"""Support for the end-to-end tests of ``infobim ifc ... --point``."""

import os
import sys
import json
import shutil
from typing import Any, Dict, List, Tuple
from pathlib import Path
from dataclasses import dataclass

import pytest
import ifcopenshell

from test.e2e.cli_process_runner import _BaseCliProcessRunner

SUPPORT_DIRECTORY: Path = Path(__file__).resolve().parent
FIXTURE_DXF: Path = SUPPORT_DIRECTORY.parent / "fixtures" / "dxf" / "floor_plan.dxf"


class IfcPointCommandRunner(_BaseCliProcessRunner):
    """Run ``infobim``; creating products runs one IFC machine per point."""

    _TIMEOUT_SECONDS: int = 600
    _EXECUTABLE_NAME: str = "infobim"


@dataclass(frozen=True)
class PointCaptureEnvironment:
    """
    The subprocess environment that drives the viewer and the NLP stand-in.

    The Qt probe plays the given capture script on the viewer window and
    writes what it saw to ``evidence_path``. Stanza is replaced by a
    deterministic stand-in answering the given language, so the dictionary
    states run without downloading models.
    """

    evidence_path: Path
    oda_log_path: Path

    @classmethod
    def install(
        cls,
        monkeypatch: pytest.MonkeyPatch,
        directory: Path,
        script: List[Dict[str, Any]],
        language: str = "pt",
    ) -> "PointCaptureEnvironment":
        bootstrap: Path = directory / "qt-point-capture-probe"
        bootstrap.mkdir()
        shutil.copyfile(
            SUPPORT_DIRECTORY / "point_capture_probe.py",
            bootstrap / "sitecustomize.py",
        )
        pythonpath: List[str] = [str(bootstrap), str(SUPPORT_DIRECTORY / "stanza_stub")]
        if "PYTHONPATH" in os.environ:
            pythonpath.append(os.environ["PYTHONPATH"])

        environment: PointCaptureEnvironment = cls(
            evidence_path=directory / "point-capture-evidence.json",
            oda_log_path=directory / "oda-conversion.json",
        )
        monkeypatch.setenv("PYTHONPATH", os.pathsep.join(pythonpath))
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
        monkeypatch.setenv("INFOBIM_E2E_STANZA_LANGUAGE", language)
        monkeypatch.setenv("INFOBIM_E2E_CAPTURE_SCRIPT", json.dumps(script))
        monkeypatch.setenv(
            "INFOBIM_E2E_CAPTURE_EVIDENCE", str(environment.evidence_path)
        )
        return environment

    def install_fake_oda_converter(
        self,
        monkeypatch: pytest.MonkeyPatch,
        directory: Path,
        converted_dxf: Path,
    ) -> None:
        converter: Path = directory / "ODAFileConverter"
        converter.write_text(
            f"#!/bin/sh\nexec {sys.executable} "
            f"{SUPPORT_DIRECTORY / 'fake_oda_converter.py'} \"$@\"\n",
            encoding="utf-8",
        )
        converter.chmod(0o755)
        monkeypatch.setenv("INFOBIM_ODA_FILE_CONVERTER", str(converter))
        monkeypatch.setenv("INFOBIM_E2E_ODA_DXF", str(converted_dxf))
        monkeypatch.setenv("INFOBIM_E2E_ODA_LOG", str(self.oda_log_path))

    def evidence(self) -> Dict[str, Any]:
        return json.loads(self.evidence_path.read_text(encoding="utf-8"))


class CaptureScript:
    """Actions of the probe, in drawing coordinates of the fixture plan."""

    @staticmethod
    def click(x: float, y: float) -> Dict[str, Any]:
        return {"action": "click", "x": x, "y": y}

    @staticmethod
    def key(name: str) -> Dict[str, Any]:
        return {"action": "key", "key": name}

    @staticmethod
    def double_click(x: float, y: float) -> Dict[str, Any]:
        return {"action": "double_click", "x": x, "y": y}

    @staticmethod
    def close() -> Dict[str, Any]:
        return {"action": "close"}


class ProjectIfcModel:
    """Read the IFC elements of a project model after the command ran."""

    @staticmethod
    def models(project: Path) -> List[Path]:
        return sorted(project.glob("*.ifc"))

    @classmethod
    def elements(cls, model_path: Path) -> Dict[str, Any]:
        model: Any = ifcopenshell.open(str(model_path))
        return {element.GlobalId: element for element in model.by_type("IfcElement")}

    @staticmethod
    def block_location(element: Any) -> Tuple[float, float, float]:
        """
        Return where the element's geometry is placed.

        The creation machine carries the position in the geometry item and
        keeps the product's own placement at the origin.
        """
        items: List[Any] = [
            item
            for representation in element.Representation.Representations
            for item in representation.Items
        ]
        assert len(items) == 1, items
        coordinates: Any = items[0].Position.Location.Coordinates
        return (float(coordinates[0]), float(coordinates[1]), float(coordinates[2]))
