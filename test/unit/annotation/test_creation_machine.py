"""Run the actual annotation FSM with real InfoBIM capabilities and Qt input."""

import json
from pathlib import Path
import yaml
from PySide6 import QtCore, QtWidgets
from ontobdc.annotation.plugin.machine.annotation_creation_from_point.machine import (
    AnnotationCreationFromPointStateTransitionHandler as Handler,
    AnnotationCreationFromPointStateEvaluatorAdapter as Evaluator,
)
from infobim.annotation.adapter.csv_repository import AnnotationCsvRepository
from infobim._2d.adapter.annotation_capabilities import DxfAnnotationCapabilities
from infobim._2d.adapter.annotation_details_form import AnnotationDetailsForm
from infobim._2d.adapter.qt_viewer import PointCaptureView
from test.unit.annotation.support import workspace


def run_machine(tmp_path, qapp):
    directory, drawing, context = workspace(tmp_path)
    for key, value in dict(
        annotation_type="note",
        file_open_path=str(drawing),
        entity_repository=AnnotationCsvRepository(),
    ).items():
        context.set_parameter_value(key, value)
    DxfAnnotationCapabilities.apply(context)
    observed_viewer_during_form = []

    def human():
        for widget in qapp.allWidgets():
            if isinstance(widget, AnnotationDetailsForm) and widget.isVisible():
                observed_viewer_during_form.append(
                    any(
                        isinstance(view, PointCaptureView) and view.isVisible()
                        for view in qapp.allWidgets()
                    )
                )
                widget.set_values(title="Review")
                widget._buttons.button(
                    QtWidgets.QDialogButtonBox.StandardButton.Ok
                ).click()
            elif (
                isinstance(widget, PointCaptureView)
                and widget._capture is not None
                and not widget._capture.finished
            ):
                widget._capture.finish(QtCore.QPointF(1.5, 2))

    timer = QtCore.QTimer()
    timer.timeout.connect(human)
    timer.start(20)
    deadline = QtCore.QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(
        lambda: [
            widget.reject()
            for widget in qapp.allWidgets()
            if isinstance(widget, AnnotationDetailsForm)
        ]
    )
    deadline.start(10000)
    try:
        result = Handler(context).execute()
    finally:
        timer.stop()
        deadline.stop()
    assert result["dataset_path"] == str(directory / "annotation")
    assert not any(
        isinstance(view, PointCaptureView) and view.isVisible()
        for view in qapp.allWidgets()
    )
    statechart = yaml.safe_load(Evaluator.statechart_file_path().read_text())[
        "statechart"
    ]["root state"]
    states = {state["name"]: state for state in statechart["states"]}
    expected = []
    state = states[statechart["initial"]]
    while state.get("transitions"):
        target = state["transitions"][0]["target"]
        expected.append(target)
        state = states[target]
    directory = tmp_path / ".__ontobdc__/etl/annotation/creation/point"
    events = sorted(directory.glob("*.json"), key=lambda file: file.stat().st_mtime_ns)
    performed = [json.loads(file.read_text())["state"].strip("_") for file in events]
    assert performed == expected
    assert AnnotationCsvRepository().rows(Path(result["dataset_path"]))

    return observed_viewer_during_form


def test_real_machine_executes_yaml_transition_order_and_closes_viewer(tmp_path, qapp):
    run_machine(tmp_path, qapp)


def test_viewer_stays_visible_while_annotation_details_are_requested(tmp_path, qapp):
    assert run_machine(tmp_path, qapp) == [True]
