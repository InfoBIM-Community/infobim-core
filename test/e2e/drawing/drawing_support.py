"""Support for the end-to-end tests of ``infobim drawing --view``."""

import os
import sys
import json
import shutil
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from test.e2e.project_workspace import ProjectE2eWorkspace
from infobim.project.adapter.contract import ProjectGuard
from infobim.drawing.adapter.taxonomy import DrawingViewNamespaces
from test.e2e.cli_process_runner import (
    _BaseCliProcessRunner,
    InfobimTerminalProcessRunner,
)

SUPPORT_DIRECTORY: Path = Path(__file__).resolve().parent
FIXTURE_SHEET: Path = SUPPORT_DIRECTORY.parent / "fixtures" / "dxf" / "A101.dxf"
FAKE_ODA_SCRIPT: Path = SUPPORT_DIRECTORY.parent / "ifc" / "fake_oda_converter.py"
CT: Namespace = DrawingViewNamespaces.CT
LS: Namespace = DrawingViewNamespaces.LS
STEP: Namespace = DrawingViewNamespaces.STEP


class DrawingCommandRunner(_BaseCliProcessRunner):
    """Run ``infobim``; a drawing run loads, extracts, models and validates."""

    _TIMEOUT_SECONDS: int = 300
    _EXECUTABLE_NAME: str = "infobim"


class DrawingTerminalRunner(InfobimTerminalProcessRunner):
    """Run ``infobim drawing ... -i`` in a pseudo-terminal."""

    _TIMEOUT_SECONDS: int = 300


class DrawingWorkspaces:
    """Projects for the drawing tests, under one shared root."""

    @staticmethod
    def create(tmp_path: Path, name: str = "project-under-test") -> ProjectE2eWorkspace:
        root: Path = tmp_path / "root"
        root.mkdir(exist_ok=True)
        return ProjectE2eWorkspace.create(root, name=name)

    @staticmethod
    def global_id(project: Path) -> str:
        global_id: Any = ProjectGuard.ifc_project_global_id(project)
        assert isinstance(global_id, str) and global_id
        return global_id


@dataclass(frozen=True)
class DrawingProbeEnvironment:
    """
    The subprocess environment that observes the interactive browser.

    The probe is installed as ``sitecustomize`` of the ``infobim``
    subprocess and records what the real browser and renderer did.
    """

    evidence_path: Path
    temporary_directory: Path
    bootstrap_directory: Path

    @classmethod
    def install(
        cls,
        monkeypatch: pytest.MonkeyPatch,
        directory: Path,
        block_qt: bool = False,
        render_delay: Optional[float] = None,
        break_shacl: bool = False,
    ) -> "DrawingProbeEnvironment":
        bootstrap: Path = directory / "drawing-view-probe"
        bootstrap.mkdir()
        shutil.copyfile(
            SUPPORT_DIRECTORY / "drawing_view_probe.py", bootstrap / "sitecustomize.py"
        )
        pythonpath: List[str] = [str(bootstrap)]
        if "PYTHONPATH" in os.environ:
            pythonpath.append(os.environ["PYTHONPATH"])
        environment: DrawingProbeEnvironment = cls(
            evidence_path=directory / "drawing-view-evidence.json",
            temporary_directory=directory / "subprocess-tmp",
            bootstrap_directory=bootstrap,
        )
        environment.temporary_directory.mkdir()
        monkeypatch.setenv("PYTHONPATH", os.pathsep.join(pythonpath))
        monkeypatch.setenv("INFOBIM_E2E_DRAWING_EVIDENCE", str(environment.evidence_path))
        monkeypatch.setenv("TMPDIR", str(environment.temporary_directory))
        if block_qt:
            monkeypatch.setenv("INFOBIM_E2E_DRAWING_BLOCK_QT", "1")
        if render_delay is not None:
            monkeypatch.setenv("INFOBIM_E2E_DRAWING_RENDER_DELAY", str(render_delay))
        if break_shacl:
            monkeypatch.setenv("INFOBIM_E2E_DRAWING_BREAK_SHACL", "1")
        return environment

    def evidence(self) -> Dict[str, Any]:
        return json.loads(self.evidence_path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class FakeOdaConverter:
    """The test-only ODA File Converter the IFC tests use, installed on its own."""

    log_path: Path

    @classmethod
    def install(
        cls,
        monkeypatch: pytest.MonkeyPatch,
        directory: Path,
        converted_dxf: Path,
    ) -> "FakeOdaConverter":
        converter: Path = directory / "ODAFileConverter"
        converter.write_text(
            f'#!/bin/sh\nexec {sys.executable} {FAKE_ODA_SCRIPT} "$@"\n',
            encoding="utf-8",
        )
        converter.chmod(0o755)
        installed: FakeOdaConverter = cls(log_path=directory / "oda-conversion.json")
        monkeypatch.setenv("INFOBIM_ODA_FILE_CONVERTER", str(converter))
        monkeypatch.setenv("INFOBIM_E2E_ODA_DXF", str(converted_dxf))
        monkeypatch.setenv("INFOBIM_E2E_ODA_LOG", str(installed.log_path))
        return installed

    def conversion(self) -> Dict[str, Any]:
        return json.loads(self.log_path.read_text(encoding="utf-8"))


class PersistedDrawingModel:
    """Read the ICDD linkset and OntoSTEP triples a drawing run persisted."""

    def __init__(self, linkset_path: Path, presentation_path: Path) -> None:
        self.linkset: Graph = Graph()
        self.linkset.parse(str(linkset_path), format="turtle")
        self.presentation: Graph = Graph()
        self.presentation.parse(str(presentation_path), format="turtle")

    def union(self) -> Graph:
        graph: Graph = Graph()
        graph += self.linkset
        graph += self.presentation
        return graph

    def document_filenames(self) -> Set[str]:
        return {
            str(self.linkset.value(document, CT.filename))
            for document in self.linkset.subjects(RDF.type, CT.InternalDocument)
        }

    def linked_filenames(self) -> Dict[str, Set[str]]:
        """Each source document's filename, with the filenames it links to."""
        links: Dict[str, Set[str]] = {}
        link: URIRef
        for link in self.linkset.subjects(RDF.type, LS.DirectedBinaryLink):
            source: str = self._filename_of_element(
                self.linkset.value(link, LS.hasFromLinkElement)
            )
            target: str = self._filename_of_element(
                self.linkset.value(link, LS.hasToLinkElement)
            )
            links.setdefault(source, set()).add(target)
        return links

    def area_names(self) -> List[str]:
        return [
            str(self.presentation.value(area, STEP["name"]))
            for area in self.presentation.subjects(RDF.type, STEP.presentation_area)
        ]

    def related_view_names(self) -> Dict[str, Set[str]]:
        """Each presentation area's name, with the views related to it."""
        related: Dict[str, Set[str]] = {}
        relationship: URIRef
        for relationship in self.presentation.subjects(
            RDF.type, STEP.representation_relationship
        ):
            area: Any = self.presentation.value(relationship, STEP.rep_1)
            view: Any = self.presentation.value(relationship, STEP.rep_2)
            assert (area, RDF.type, STEP.presentation_area) in self.presentation
            assert (view, RDF.type, STEP.presentation_view) in self.presentation
            related.setdefault(str(self.presentation.value(area, STEP["name"])), set()).add(
                str(self.presentation.value(view, STEP["name"]))
            )
        return related

    def _filename_of_element(self, element: Any) -> str:
        assert (element, RDF.type, LS.LinkElement) in self.linkset
        document: Any = self.linkset.value(element, LS.hasDocument)
        assert (document, RDF.type, CT.InternalDocument) in self.linkset
        return str(self.linkset.value(document, CT.filename))


class WorkspaceFiles:
    """The files under a directory, to compare what a run created."""

    @staticmethod
    def of(directory: Path) -> Set[str]:
        return {
            path.relative_to(directory).as_posix()
            for path in directory.rglob("*")
            if path.is_file()
        }
