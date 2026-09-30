import hashlib
from typing import Any, Dict, List, Set
from pathlib import Path

import ezdxf
import pytest

from ontobdc.shared.adapter.shacl import ShaclValidator
from ontobdc.shared.domain.model.shacl import ShaclValidationReport

from test.e2e.project_workspace import ProjectE2eWorkspace
from test.e2e.cli_process_runner import CliInvocationResult, TerminalStep
from infobim.drawing.adapter.view_relationship import DrawingViewShapes
from test.e2e.drawing.drawing_support import (
    FIXTURE_SHEET,
    WorkspaceFiles,
    FakeOdaConverter,
    DrawingWorkspaces,
    DrawingCommandRunner,
    DrawingTerminalRunner,
    PersistedDrawingModel,
    DrawingProbeEnvironment,
)

EXPECTED_VIEWS: Dict[str, str] = {
    "PLANTA BAIXA GERAL": "PLAN_VIEW",
    "CORTE A-A": "SECTION_VIEW",
    "DETALHE 03": "DETAIL_VIEW",
}
DOWN: str = "\x1b[B"
UP: str = "\x1b[A"
QUIT: str = "q"
ESCAPE: str = "\x1b"
EMPTY_PREVIEW: str = "Select a Drawing View"
PREVIEW_GLYPH: str = "⣿"
# A preview of the fixture's views renders in well under a second.
RENDER_SECONDS: float = 3.0


class TestDrawingViewCommand:
    """
    ``infobim drawing [--global-id <id>] --view <sheet> [-i|--interactive]``.

    Every test runs the real CLI, in a subprocess or in a pseudo-terminal:
    the sheet goes through the discovery, extraction, ICDD and OntoSTEP
    modelling and SHACL validation, and what the run left in the project is
    read back from disk. The interactive tests observe the real browser and
    renderer through a probe installed in the subprocess.
    """

    # ------------------------------------------------------------ plain mode

    def test_dxf_views_are_discovered_extracted_and_modelled(
        self, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        global_id: str = DrawingWorkspaces.global_id(workspace.project)

        result: CliInvocationResult = DrawingCommandRunner(workspace.root).run(
            "drawing", "--global-id", global_id, "--view", str(FIXTURE_SHEET)
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        content: Dict[str, Any] = result.json["content"]
        assert content["global_id"] == global_id
        assert content["drawing"] == str(FIXTURE_SHEET)
        assert content["relationships_modeled"] is True
        assert content["shacl_conforms"] is True
        views: List[Dict[str, Any]] = content["views"]
        assert {view["title"]: view["kind"] for view in views} == EXPECTED_VIEWS
        self._assert_extracted(views, workspace.project)
        assert content["tree"]["name"] == FIXTURE_SHEET.name
        assert self._titles(content["tree"]["children"], "name") == sorted(EXPECTED_VIEWS)

    def test_icdd_and_ontostep_are_persisted_and_conform_to_shacl(
        self, tmp_path: Path
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)

        result: CliInvocationResult = DrawingCommandRunner(workspace.root).run(
            "drawing",
            "--global-id",
            DrawingWorkspaces.global_id(workspace.project),
            "--view",
            str(FIXTURE_SHEET),
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        content: Dict[str, Any] = result.json["content"]
        model: PersistedDrawingModel = self._persisted(content, workspace.project)
        view_files: Set[str] = {Path(view["path"]).name for view in content["views"]}
        assert model.document_filenames() == {FIXTURE_SHEET.name} | view_files
        assert model.linked_filenames() == {FIXTURE_SHEET.name: view_files}
        assert model.area_names() == [FIXTURE_SHEET.stem]
        assert model.related_view_names() == {FIXTURE_SHEET.stem: set(EXPECTED_VIEWS)}
        report: ShaclValidationReport = ShaclValidator.validate(
            model.union(), DrawingViewShapes.graph()
        )
        assert report.conforms, report.text

    def test_global_id_is_optional_inside_the_project(self, tmp_path: Path) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)

        result: CliInvocationResult = DrawingCommandRunner(workspace.project).run(
            "drawing", "--view", str(FIXTURE_SHEET)
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        content: Dict[str, Any] = result.json["content"]
        self._assert_extracted(content["views"], workspace.project)
        self._persisted(content, workspace.project)

    def test_global_id_selects_the_project_independently_of_the_directory(
        self, tmp_path: Path
    ) -> None:
        selected: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path, "project-a")
        other: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path, "project-b")
        other_before: Dict[str, bytes] = other.snapshot()

        result: CliInvocationResult = DrawingCommandRunner(other.project).run(
            "drawing",
            "--global-id",
            DrawingWorkspaces.global_id(selected.project),
            "--view",
            str(FIXTURE_SHEET),
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        content: Dict[str, Any] = result.json["content"]
        self._assert_extracted(content["views"], selected.project)
        self._persisted(content, selected.project)
        assert other.snapshot() == other_before

    @pytest.mark.parametrize(
        "order",
        [
            ["--view", "SHEET", "--global-id", "ID"],
            ["--global-id", "ID", "--view", "SHEET"],
        ],
    )
    def test_flags_are_accepted_in_any_order(
        self, tmp_path: Path, order: List[str]
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        values: Dict[str, str] = {
            "SHEET": str(FIXTURE_SHEET),
            "ID": DrawingWorkspaces.global_id(workspace.project),
        }

        result: CliInvocationResult = DrawingCommandRunner(workspace.root).run(
            "drawing", *[values.get(arg, arg) for arg in order]
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert {
            view["title"] for view in result.json["content"]["views"]
        } == set(EXPECTED_VIEWS)

    def test_dwg_is_converted_but_stays_the_modelled_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        sheet: Path = tmp_path / "A101.dwg"
        sheet.write_bytes(b"AC1032 end-to-end DWG placeholder")
        oda: FakeOdaConverter = FakeOdaConverter.install(
            monkeypatch, tmp_path, FIXTURE_SHEET
        )

        result: CliInvocationResult = DrawingCommandRunner(workspace.root).run(
            "drawing",
            "--global-id",
            DrawingWorkspaces.global_id(workspace.project),
            "--view",
            str(sheet),
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert oda.conversion()["input"].endswith(".dwg")
        content: Dict[str, Any] = result.json["content"]
        assert content["drawing"] == str(sheet)
        assert content["tree"]["name"] == "A101.dwg"
        assert {view["title"] for view in content["views"]} == set(EXPECTED_VIEWS)
        # The views were read from the converted DXF: their directory is
        # addressed by its content, which is the DXF the converter wrote.
        converted_digest: str = hashlib.sha256(FIXTURE_SHEET.read_bytes()).hexdigest()
        assert Path(content["views_directory"]).name == converted_digest
        self._assert_extracted(content["views"], workspace.project)
        model: PersistedDrawingModel = self._persisted(content, workspace.project)
        assert FIXTURE_SHEET.name not in model.document_filenames()
        assert set(model.linked_filenames()) == {"A101.dwg"}
        assert model.area_names() == ["A101"]

    def test_unsupported_input_fails_without_views(self, tmp_path: Path) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        notes: Path = tmp_path / "notes.txt"
        notes.write_text("not a drawing\n", encoding="utf-8")
        before: Set[str] = WorkspaceFiles.of(workspace.project)

        result: CliInvocationResult = DrawingCommandRunner(workspace.root).run(
            "drawing",
            "--global-id",
            DrawingWorkspaces.global_id(workspace.project),
            "--view",
            str(notes),
        )

        assert result.exit_code == 1, result.stdout
        assert "text/plain" in result.json["content"]["error"]
        created: Set[str] = WorkspaceFiles.of(workspace.project) - before
        assert not any("/etl/view/" in path for path in created), created
        assert not any("/payload/linkset/" in path for path in created), created
        assert not any(
            "/payload/triple/" in path and not path.endswith("ifc_project.ttl")
            for path in created
        ), created

    # ------------------------------------------------------ interactive mode

    @pytest.mark.parametrize("interactive_flag", ["-i", "--interactive"])
    def test_interactive_opens_the_browser_and_quits(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        interactive_flag: str,
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        probe: DrawingProbeEnvironment = DrawingProbeEnvironment.install(
            monkeypatch, tmp_path
        )

        result: CliInvocationResult = DrawingTerminalRunner(workspace.root).run(
            "drawing",
            "--global-id",
            DrawingWorkspaces.global_id(workspace.project),
            "--view",
            str(FIXTURE_SHEET),
            interactive_flag,
            ready_marker=EMPTY_PREVIEW,
            keys=QUIT,
        )

        assert result.exit_code == 0, result.stdout
        evidence: Dict[str, Any] = probe.evidence()
        assert evidence["app_started"] is True
        assert evidence["root_label"] == FIXTURE_SHEET.name
        assert FIXTURE_SHEET.name in result.stdout
        title: str
        for title in EXPECTED_VIEWS:
            assert title in result.stdout
        assert self._titles(evidence["leaves"], "label") == sorted(EXPECTED_VIEWS)
        # The root starts highlighted: the pane asks for a view and the sheet
        # itself is never handed to the renderer.
        assert evidence["displays"][0] == {"kind": "message", "text": EMPTY_PREVIEW}
        assert evidence["renders"] == []

    def test_interactive_flags_are_accepted_in_any_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        probe: DrawingProbeEnvironment = DrawingProbeEnvironment.install(
            monkeypatch, tmp_path
        )

        result: CliInvocationResult = DrawingTerminalRunner(workspace.root).run(
            "drawing",
            "-i",
            "--view",
            str(FIXTURE_SHEET),
            "--global-id",
            DrawingWorkspaces.global_id(workspace.project),
            ready_marker=EMPTY_PREVIEW,
            keys=ESCAPE,
        )

        assert result.exit_code == 0, result.stdout
        assert probe.evidence()["app_started"] is True

    def test_cursor_down_previews_the_view(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        probe: DrawingProbeEnvironment = DrawingProbeEnvironment.install(
            monkeypatch, tmp_path
        )

        result: CliInvocationResult = DrawingTerminalRunner(workspace.project).run(
            "drawing",
            "--view",
            str(FIXTURE_SHEET),
            "--interactive",
            ready_marker=EMPTY_PREVIEW,
            steps=[TerminalStep(DOWN, wait_for=PREVIEW_GLYPH)],
            keys=QUIT,
        )

        assert result.exit_code == 0, result.stdout
        evidence: Dict[str, Any] = probe.evidence()
        first: Dict[str, Any] = evidence["leaves"][0]
        assert evidence["renders"] == [first["path"]]
        assert evidence["displays"][-1] == {"kind": "preview", "highlighted": first["path"]}
        assert evidence["final_cursor"] == first["label"]

    def test_fast_navigation_shows_only_the_last_view(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        probe: DrawingProbeEnvironment = DrawingProbeEnvironment.install(
            monkeypatch, tmp_path, render_delay=1.0
        )

        result: CliInvocationResult = DrawingTerminalRunner(workspace.project).run(
            "drawing",
            "--view",
            str(FIXTURE_SHEET),
            "-i",
            ready_marker=EMPTY_PREVIEW,
            steps=[TerminalStep(DOWN * 3, wait_for=PREVIEW_GLYPH, pause_seconds=4.0)],
            keys=QUIT,
        )

        assert result.exit_code == 0, result.stdout
        evidence: Dict[str, Any] = probe.evidence()
        last: Dict[str, Any] = evidence["leaves"][-1]
        assert evidence["final_highlighted"] == last["path"]
        assert evidence["final_cursor"] == last["label"]
        previews: List[Dict[str, Any]] = [
            display for display in evidence["displays"] if display["kind"] == "preview"
        ]
        assert previews == [{"kind": "preview", "highlighted": last["path"]}]
        # A render of a view the cursor only passed over may still finish
        # after it moved on; none of them may reach the preview pane.
        assert all(
            stale["highlighted"] == last["path"] and stale["rendered"] != last["path"]
            for stale in evidence["stale_completions"]
        )

    def test_revisited_view_is_served_from_the_session_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        probe: DrawingProbeEnvironment = DrawingProbeEnvironment.install(
            monkeypatch, tmp_path
        )

        result: CliInvocationResult = DrawingTerminalRunner(workspace.project).run(
            "drawing",
            "--view",
            str(FIXTURE_SHEET),
            "-i",
            ready_marker=EMPTY_PREVIEW,
            steps=[
                TerminalStep(DOWN, pause_seconds=RENDER_SECONDS),
                TerminalStep(DOWN, pause_seconds=RENDER_SECONDS),
                TerminalStep(UP, pause_seconds=RENDER_SECONDS),
            ],
            keys=QUIT,
        )

        assert result.exit_code == 0, result.stdout
        evidence: Dict[str, Any] = probe.evidence()
        first: str = evidence["leaves"][0]["path"]
        second: str = evidence["leaves"][1]["path"]
        assert evidence["renders"] == [first, second]
        assert [
            display["highlighted"]
            for display in evidence["displays"]
            if display["kind"] == "preview"
        ] == [first, second, first]

    def test_previews_stay_in_memory_and_qt_is_never_loaded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        first_run: CliInvocationResult = DrawingCommandRunner(workspace.root).run(
            "drawing",
            "--global-id",
            DrawingWorkspaces.global_id(workspace.project),
            "--view",
            str(FIXTURE_SHEET),
        )
        assert first_run.exit_code == 0, first_run.stdout + first_run.stderr
        probe: DrawingProbeEnvironment = DrawingProbeEnvironment.install(
            monkeypatch, tmp_path, block_qt=True
        )
        before: Set[str] = WorkspaceFiles.of(tmp_path)

        result: CliInvocationResult = DrawingTerminalRunner(workspace.root).run(
            "drawing",
            "--global-id",
            DrawingWorkspaces.global_id(workspace.project),
            "--view",
            str(FIXTURE_SHEET),
            "-i",
            ready_marker=EMPTY_PREVIEW,
            steps=[
                TerminalStep(DOWN, pause_seconds=RENDER_SECONDS),
                TerminalStep(DOWN, pause_seconds=RENDER_SECONDS),
                TerminalStep(DOWN, pause_seconds=RENDER_SECONDS),
            ],
            keys=QUIT,
        )

        assert result.exit_code == 0, result.stdout
        evidence: Dict[str, Any] = probe.evidence()
        assert evidence["qt_import_attempts"] == []
        assert len(evidence["renders"]) == len(EXPECTED_VIEWS)
        # Only the probe's own files are new: the rerun rewrote the views,
        # linkset and triples under the names the first run gave them.
        created: Set[str] = {
            path
            for path in WorkspaceFiles.of(tmp_path) - before
            if not path.startswith(f"{probe.bootstrap_directory.name}/")
        }
        assert created == {probe.evidence_path.relative_to(tmp_path).as_posix()}, created
        assert list(probe.temporary_directory.iterdir()) == []

    def test_interactive_dwg_keeps_the_dwg_as_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        sheet: Path = tmp_path / "A101.dwg"
        sheet.write_bytes(b"AC1032 end-to-end DWG placeholder")
        oda: FakeOdaConverter = FakeOdaConverter.install(
            monkeypatch, tmp_path, FIXTURE_SHEET
        )
        probe: DrawingProbeEnvironment = DrawingProbeEnvironment.install(
            monkeypatch, tmp_path, block_qt=True
        )

        result: CliInvocationResult = DrawingTerminalRunner(workspace.root).run(
            "drawing",
            "--global-id",
            DrawingWorkspaces.global_id(workspace.project),
            "--view",
            str(sheet),
            "-i",
            ready_marker=EMPTY_PREVIEW,
            steps=[TerminalStep(DOWN, wait_for=PREVIEW_GLYPH)],
            keys=QUIT,
        )

        assert result.exit_code == 0, result.stdout
        assert oda.conversion()["input"].endswith(".dwg")
        evidence: Dict[str, Any] = probe.evidence()
        assert evidence["root_label"] == "A101.dwg"
        assert "A101.dwg" in result.stdout
        assert evidence["qt_import_attempts"] == []
        rendered: Path = Path(evidence["renders"][0])
        assert rendered.suffix == ".dxf"
        assert rendered.is_relative_to(workspace.project)
        assert rendered.stem in EXPECTED_VIEWS

    def test_shacl_violation_fails_before_the_browser_opens(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        probe: DrawingProbeEnvironment = DrawingProbeEnvironment.install(
            monkeypatch, tmp_path, break_shacl=True
        )

        result: CliInvocationResult = DrawingTerminalRunner(workspace.root).run(
            "drawing",
            "--global-id",
            DrawingWorkspaces.global_id(workspace.project),
            "--view",
            str(FIXTURE_SHEET),
            "-i",
            ready_marker=EMPTY_PREVIEW,
            keys=QUIT,
        )

        assert result.exit_code == 1, result.stdout
        assert "SHACL" in result.stdout
        assert "PresentationViewShape" in result.stdout.replace("\n", "").replace(" ", "")
        assert EMPTY_PREVIEW not in result.stdout
        assert not probe.evidence_path.exists()
        payload: Path = workspace.project / ".__infobim__" / "payload"
        assert list((payload / "linkset").glob("*.ttl")) == []
        assert [path.name for path in (payload / "triple").glob("*.ttl")] == [
            "ifc_project.ttl"
        ]

    def test_interactive_unsupported_input_never_opens_the_browser(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        workspace: ProjectE2eWorkspace = DrawingWorkspaces.create(tmp_path)
        notes: Path = tmp_path / "notes.txt"
        notes.write_text("not a drawing\n", encoding="utf-8")
        probe: DrawingProbeEnvironment = DrawingProbeEnvironment.install(
            monkeypatch, tmp_path
        )

        result: CliInvocationResult = DrawingTerminalRunner(workspace.project).run(
            "drawing",
            "--view",
            str(notes),
            "--interactive",
            ready_marker=EMPTY_PREVIEW,
            keys=QUIT,
        )

        assert result.exit_code == 1, result.stdout
        assert EMPTY_PREVIEW not in result.stdout
        assert not probe.evidence_path.exists()

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _titles(nodes: List[Dict[str, Any]], key: str) -> List[str]:
        """The view titles of tree nodes labelled ``TITLE [KIND] scale``."""
        return sorted(node[key].split(" [")[0] for node in nodes)

    @staticmethod
    def _assert_extracted(views: List[Dict[str, Any]], project: Path) -> None:
        assert {view["title"] for view in views} == set(EXPECTED_VIEWS)
        view: Dict[str, Any]
        for view in views:
            path: Path = Path(view["path"])
            assert path.is_file()
            assert path.is_relative_to(project)
            assert path.name == f"{view['title']}.dxf"
            assert len(list(ezdxf.readfile(str(path)).modelspace())) > 0

    @staticmethod
    def _persisted(content: Dict[str, Any], project: Path) -> PersistedDrawingModel:
        relationships: Dict[str, Any] = content["relationships"]
        linkset: Path = Path(relationships["linkset_path"])
        presentation: Path = Path(relationships["presentation_path"])
        payload: Path = project / ".__infobim__" / "payload"
        assert linkset.is_file() and linkset.parent == payload / "linkset"
        assert presentation.is_file() and presentation.parent == payload / "triple"
        return PersistedDrawingModel(linkset, presentation)
