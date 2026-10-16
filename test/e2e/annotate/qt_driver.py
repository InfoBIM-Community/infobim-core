"""Simulate the human in Qt, then run the actual CLI entry point unchanged."""

import contextlib
import os
import sys
from pathlib import Path

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as error:
    raise RuntimeError(
        "Annotation tests require PySide6-Essentials and QT_QPA_PLATFORM=offscreen"
    ) from error
with contextlib.redirect_stdout(sys.stderr):
    from infobim._2d.adapter.annotation_details_form import AnnotationDetailsForm
    from infobim._2d.adapter.qt_viewer import PointCaptureView

if os.environ.get("ANNOTATION_TEST_CATALOG"):
    from brasidatacenter import resources

    # External ontology-resource boundary: a copied, deliberately ambiguous catalog.
    resources.ontology_root = lambda: Path(os.environ["ANNOTATION_TEST_CATALOG"])

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
app.setQuitOnLastWindowClosed(False)
mode = os.environ.get("ANNOTATION_TEST_MODE", "accept")
seen = set()


def drive():
    for widget in app.allWidgets():
        if (
            isinstance(widget, AnnotationDetailsForm)
            and widget.isVisible()
            and id(widget) not in seen
        ):
            seen.add(id(widget))
            if mode == "cancel":
                widget._buttons.button(
                    QtWidgets.QDialogButtonBox.StandardButton.Cancel
                ).click()
            elif mode == "blank-title":
                widget.set_values(title=" \t ", text="Optional body", author="Elias")
                ok = widget._buttons.button(
                    QtWidgets.QDialogButtonBox.StandardButton.Ok
                )
                print(
                    f"ANNOTATION_TEST_BLANK_TITLE_ENABLED={ok.isEnabled()}",
                    file=sys.stderr,
                    flush=True,
                )
                ok.click()
                widget._buttons.button(
                    QtWidgets.QDialogButtonBox.StandardButton.Cancel
                ).click()
            else:
                widget.set_values(
                    title="  Review drawing  ",
                    text='Body, "quoted"\nsecond line',
                    author="  Elias  ",
                )
                widget._buttons.button(
                    QtWidgets.QDialogButtonBox.StandardButton.Ok
                ).click()
        elif isinstance(widget, PointCaptureView):
            capture = widget._capture
            if capture is not None and not capture.finished:
                capture.click(QtCore.QPointF(1.5, 2))
                capture.click(QtCore.QPointF(99, 99))
                capture.finish(QtCore.QPointF(3, 4))


timer = QtCore.QTimer()
timer.timeout.connect(drive)
timer.start(20)
# A broken flow must fail, never leave the subprocess waiting for a human.
QtCore.QTimer.singleShot(20000, lambda: os._exit(124))
from infobim.cli import main

main()
