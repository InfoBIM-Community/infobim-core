"""
Subprocess bootstrap that drives the point capture of the 2D viewer.

Installed as ``sitecustomize`` in the ``infobim`` subprocess by the
end-to-end tests. When the viewer runs a dialog with a point capture bound
to its view, the probe plays the actions of ``INFOBIM_E2E_CAPTURE_SCRIPT``
with ``QTest`` on that same window, waiting on real conditions (a marker
appearing or disappearing, the dialog closing) instead of fixed sleeps. It
writes what it saw to ``INFOBIM_E2E_CAPTURE_EVIDENCE``. A watchdog closes
the window if the script stalls, so the command fails instead of hanging.
"""

import os
import json
import time
from typing import Any, Callable, ClassVar, Dict, List
from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QPoint, QPointF, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsSimpleTextItem,
)


class PointCaptureProbe:
    WAIT_SECONDS: ClassVar[float] = 10.0
    WATCHDOG_MILLISECONDS: ClassVar[int] = 60_000
    KEYS: ClassVar[Dict[str, Any]] = {
        "backspace": Qt.Key.Key_Backspace,
        "delete": Qt.Key.Key_Delete,
    }
    original_exec: ClassVar[Callable[..., int]] = QDialog.exec
    original_init: ClassVar[Callable[..., None]] = QDialog.__init__
    dialogs: ClassVar[List[QDialog]] = []

    def __init__(self, dialog: QDialog, view: Any) -> None:
        self._dialog: QDialog = dialog
        self._view: Any = view
        self._evidence: Dict[str, Any] = {
            "dialogs_created": len(self.dialogs),
            "dialog_index": self.dialogs.index(dialog),
            "steps": [],
            "error": None,
        }

    @classmethod
    def install(cls) -> None:
        QDialog.__init__ = cls._init
        QDialog.exec = cls._exec

    @staticmethod
    def _init(dialog: QDialog, *args: Any, **kwargs: Any) -> None:
        PointCaptureProbe.original_init(dialog, *args, **kwargs)
        PointCaptureProbe.dialogs.append(dialog)

    @staticmethod
    def _exec(dialog: QDialog) -> int:
        from infobim._2d.adapter.qt_viewer import PointCaptureView

        views: List[Any] = dialog.findChildren(PointCaptureView)
        if views and views[0]._capture is not None:
            probe: PointCaptureProbe = PointCaptureProbe(dialog, views[0])
            QTimer.singleShot(0, probe.play)
            QTimer.singleShot(PointCaptureProbe.WATCHDOG_MILLISECONDS, dialog.reject)
        return PointCaptureProbe.original_exec(dialog)

    def play(self) -> None:
        try:
            self._wait_until(lambda: self._dialog.isVisible() and self._view.isVisible())
            action: Dict[str, Any]
            for action in json.loads(os.environ["INFOBIM_E2E_CAPTURE_SCRIPT"]):
                self._perform(action)
        except Exception as error:
            self._evidence["error"] = f"{type(error).__name__}: {error}"
            self._dialog.reject()
        finally:
            Path(os.environ["INFOBIM_E2E_CAPTURE_EVIDENCE"]).write_text(
                json.dumps(self._evidence), encoding="utf-8"
            )

    def _perform(self, action: Dict[str, Any]) -> None:
        kind: str = action["action"]
        before: int = len(self._markers())
        if kind == "click":
            QTest.mouseClick(
                self._view.viewport(),
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                self._pixel(action),
            )
            self._wait_until(lambda: len(self._markers()) == before + 1)
        elif kind == "key":
            QTest.keyClick(self._view, self.KEYS[action["key"]])
            self._wait_until(lambda: len(self._markers()) == max(before - 1, 0))
        elif kind == "double_click":
            QTest.mouseDClick(
                self._view.viewport(),
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                self._pixel(action),
            )
        elif kind == "close":
            self._dialog.reject()
        else:
            raise ValueError(f"Unknown capture action: {kind}")
        self._evidence["steps"].append({"action": action, "markers": self._markers()})

    def _pixel(self, action: Dict[str, Any]) -> QPoint:
        return self._view.mapFromScene(QPointF(float(action["x"]), float(action["y"])))

    def _markers(self) -> List[Dict[str, Any]]:
        if self._view.scene() is None:
            return []
        markers: List[Dict[str, Any]] = []
        item: Any
        for item in self._view.scene().items():
            if not isinstance(item, QGraphicsEllipseItem):
                continue
            labels: List[str] = [
                child.text()
                for child in item.childItems()
                if isinstance(child, QGraphicsSimpleTextItem)
            ]
            markers.append(
                {
                    "x": item.pos().x(),
                    "y": item.pos().y(),
                    "color": item.brush().color().name(),
                    "labels": labels,
                }
            )
        return sorted(markers, key=lambda marker: (marker["x"], marker["y"]))

    def _wait_until(self, condition: Callable[[], bool]) -> None:
        deadline: float = time.monotonic() + self.WAIT_SECONDS
        while not condition():
            if time.monotonic() > deadline:
                raise TimeoutError("The viewer did not reach the expected state.")
            QApplication.processEvents()
            QTest.qWait(10)


PointCaptureProbe.install()
