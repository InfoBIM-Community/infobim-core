"""
Subprocess bootstrap that observes ``infobim drawing ... -i`` from inside.

Installed as ``sitecustomize`` in the ``infobim`` subprocess by the
end-to-end tests, only for the ``infobim`` executable. It never replaces
the discovery, the renderer or the view browser: it wraps them to record
what they did, and writes that evidence to ``INFOBIM_E2E_DRAWING_EVIDENCE``
when the browser exits. Each wrapper calls the real method.

Optional behaviours, each enabled by its own environment variable:

``INFOBIM_E2E_DRAWING_BLOCK_QT``
    Any import of PySide6, PyQt or shiboken fails, and is recorded.
``INFOBIM_E2E_DRAWING_RENDER_DELAY``
    Seconds each real preview rendering is held before it returns, so a
    fast navigation deterministically outruns the renderer.
``INFOBIM_E2E_DRAWING_BREAK_SHACL``
    Each presentation view gets a second ``step:name``, which the canonical
    SHACL shapes reject.
"""

import os
import sys
import json
import time
from typing import Any, Callable, ClassVar, Dict, List, Optional, Sequence
from pathlib import Path
import threading
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec


class QtImportBlocker(MetaPathFinder):
    BLOCKED: ClassVar[Sequence[str]] = ("PySide6", "PyQt5", "PyQt6", "shiboken6")
    attempts: ClassVar[List[str]] = []

    def find_spec(
        self, fullname: str, path: Any = None, target: Any = None
    ) -> Optional[ModuleSpec]:
        if fullname.split(".")[0] in self.BLOCKED:
            QtImportBlocker.attempts.append(fullname)
            raise ImportError(f"Qt is blocked in this end-to-end test: {fullname}")
        return None


class DrawingViewProbe:
    evidence: ClassVar[Dict[str, Any]] = {
        "app_started": False,
        "root_label": None,
        "leaves": [],
        "renders": [],
        "displays": [],
        "stale_completions": [],
        "final_highlighted": None,
        "final_cursor": None,
        "qt_import_attempts": QtImportBlocker.attempts,
    }
    lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def install(cls) -> None:
        from infobim.drawing.adapter.view_preview import DxfPreviewRenderer
        from infobim._drawing_interactive.adapter.view_browser import DrawingViewBrowserApp

        cls._wrap_renderer(DxfPreviewRenderer)
        cls._wrap_browser(DrawingViewBrowserApp)
        if os.environ.get("INFOBIM_E2E_DRAWING_BREAK_SHACL"):
            cls._break_presentation_names()

    @classmethod
    def _wrap_renderer(cls, renderer: Any) -> None:
        original: Callable[..., bytes] = renderer.render
        delay: float = float(os.environ.get("INFOBIM_E2E_DRAWING_RENDER_DELAY", "0"))

        def render(self: Any, dxf_path: Path) -> bytes:
            rendered: bytes = original(self, dxf_path)
            time.sleep(delay)
            with cls.lock:
                cls.evidence["renders"].append(str(dxf_path))
            return rendered

        renderer.render = render

    @classmethod
    def _wrap_browser(cls, browser: Any) -> None:
        original_run: Callable[..., Any] = browser.run
        original_mount: Callable[..., Any] = browser.on_mount
        original_rendered: Callable[..., Any] = browser._show_rendered
        original_preview: Callable[..., Any] = browser._show_preview
        original_message: Callable[..., Any] = browser._show_message

        def run(self: Any, *args: Any, **kwargs: Any) -> Any:
            cls.evidence["app_started"] = True
            try:
                return original_run(self, *args, **kwargs)
            finally:
                cls._write()

        def on_mount(self: Any) -> None:
            original_mount(self)
            tree: Any = self.query_one("#views")
            cls.evidence["root_label"] = tree.root.label.plain
            cls.evidence["leaves"] = [
                {"label": node.label.plain, "path": node.data.path}
                for node in tree.root.children
            ]

        def show_rendered(self: Any, path: str, rendered: bytes) -> None:
            if path != self._highlighted:
                cls.evidence["stale_completions"].append(
                    {"rendered": path, "highlighted": self._highlighted}
                )
            original_rendered(self, path, rendered)

        def show_preview(self: Any, rendered: bytes) -> None:
            original_preview(self, rendered)
            cls.evidence["displays"].append(
                {"kind": "preview", "highlighted": self._highlighted}
            )
            cls._record_cursor(self)

        def show_message(self: Any, message: str) -> None:
            original_message(self, message)
            cls.evidence["displays"].append({"kind": "message", "text": message})
            cls._record_cursor(self)

        browser.run = run
        browser.on_mount = on_mount
        browser._show_rendered = show_rendered
        browser._show_preview = show_preview
        browser._show_message = show_message

    @classmethod
    def _record_cursor(cls, app: Any) -> None:
        cls.evidence["final_highlighted"] = app._highlighted
        cursor: Any = app.query_one("#views").cursor_node
        cls.evidence["final_cursor"] = None if cursor is None else cursor.label.plain

    @staticmethod
    def _break_presentation_names() -> None:
        from rdflib import Literal
        from infobim.drawing.adapter.taxonomy import DrawingViewNamespaces
        from infobim.drawing.adapter.step_presentation import OntoStepPresentation

        original: Callable[..., None] = OntoStepPresentation.presentation_view

        def presentation_view(graph: Any, view: Any, name: str) -> None:
            original(graph, view, name)
            graph.add((view, DrawingViewNamespaces.STEP["name"], Literal("second name")))

        OntoStepPresentation.presentation_view = staticmethod(presentation_view)

    @classmethod
    def _write(cls) -> None:
        with cls.lock:
            Path(os.environ["INFOBIM_E2E_DRAWING_EVIDENCE"]).write_text(
                json.dumps(cls.evidence), encoding="utf-8"
            )


if Path(sys.argv[0]).name == "infobim":
    if os.environ.get("INFOBIM_E2E_DRAWING_BLOCK_QT"):
        sys.meta_path.insert(0, QtImportBlocker())
    DrawingViewProbe.install()
