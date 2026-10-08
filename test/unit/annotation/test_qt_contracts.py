"""Real Qt form and point-capture contracts without a viewer double."""

import pytest
from PySide6 import QtCore, QtWidgets
from infobim._2d.adapter.annotation_details_form import AnnotationDetailsForm
from infobim._2d.adapter.qt_viewer import PointCaptureView, DxfPointCapture


@pytest.mark.parametrize(
    "title,enabled", [("", False), (" \t ", False), (" Review ", True)]
)
def test_ok_requires_nonblank_title(qapp, title, enabled):
    form = AnnotationDetailsForm()
    try:
        form.set_values(title=title)
        assert (
            form._buttons.button(
                QtWidgets.QDialogButtonBox.StandardButton.Ok
            ).isEnabled()
            is enabled
        )
    finally:
        form.close()


def test_details_trim_values_and_omit_blank_optionals(qapp):
    form = AnnotationDetailsForm()
    try:
        form.set_values(title=" Review ", text=" \n ", author=" ")
        assert form.details() == {"title": "Review"}
        form.set_values(title=" Review ", text=" Body \n ", author=" Elias ")
        assert form.details() == dict(title="Review", text="Body", author="Elias")
    finally:
        form.close()


def test_immediate_pre_double_click_is_discarded_and_previous_click_retained(qapp):
    view = PointCaptureView()
    view.setScene(QtWidgets.QGraphicsScene(view))
    completed = []
    capture = DxfPointCapture(view, lambda: completed.append(True))
    try:
        capture.click(QtCore.QPointF(1.5, 2))
        capture.click(QtCore.QPointF(99, 99))
        capture.finish(QtCore.QPointF(3, 4))
        assert capture.points() == [dict(x=1.5, y=2), dict(x=3, y=4)]
        assert capture.finished and completed == [True]
    finally:
        capture.detach()
        view.close()


def test_cancelled_details_session_raises_runtime_error(qapp, tmp_path):
    import ezdxf
    from infobim._2d.adapter.qt_viewer import DxfViewerSession

    # The public session is exercised with an actual loaded Drawing.
    drawing = ezdxf.new()
    session = DxfViewerSession(
        {"original": drawing}, (("original", "Original", "drawing"),)
    )
    timer = QtCore.QTimer()

    def cancel():
        for widget in qapp.allWidgets():
            if isinstance(widget, AnnotationDetailsForm) and widget.isVisible():
                widget._buttons.button(
                    QtWidgets.QDialogButtonBox.StandardButton.Cancel
                ).click()

    timer.timeout.connect(cancel)
    timer.start(20)
    try:
        with pytest.raises(RuntimeError, match="cancelled"):
            session.request_annotation_details()
    finally:
        timer.stop()
        session.close()


@pytest.mark.parametrize("mode", ["annotation", "ifc"])
def test_point_capabilities_keep_annotation_window_but_close_ifc_window(
    qapp, tmp_path, mode
):
    import ezdxf
    from infobim._2d.adapter.qt_viewer import DxfViewerSession
    from infobim._2d.plugin.capability.loader.annotation_points import (
        DxfAnnotationPointsCapability,
    )
    from infobim._2d.plugin.capability.loader.points import PointsCapturedCapability

    drawing = ezdxf.new()
    session = DxfViewerSession(
        {"original": drawing}, (("original", "Original", "drawing"),)
    )
    from test.unit.annotation.support import context as make_context

    context = make_context(tmp_path)
    context.set_parameter_value("dxf_viewer_session", session)
    session.show()
    timer = QtCore.QTimer()

    def finish():
        for widget in qapp.allWidgets():
            if (
                isinstance(widget, PointCaptureView)
                and widget._capture is not None
                and not widget._capture.finished
            ):
                widget._capture.finish(QtCore.QPointF(1.5, 2))

    timer.timeout.connect(finish)
    timer.start(20)
    try:
        capability = (
            DxfAnnotationPointsCapability()
            if mode == "annotation"
            else PointsCapturedCapability()
        )
        result = capability.execute(context)
        assert result["captured_points"] == [dict(x=1.5, y=2)]
        import shiboken6

        QtCore.QCoreApplication.sendPostedEvents(
            None, QtCore.QEvent.Type.DeferredDelete
        )
        assert shiboken6.isValid(session._dialog) is (mode == "annotation")
        if mode == "annotation":
            assert session._dialog.isVisible()
    finally:
        timer.stop()
        import shiboken6

        if shiboken6.isValid(session._dialog):
            session.close()


def test_annotation_details_cancel_always_closes_viewer(qapp, tmp_path):
    import ezdxf
    from infobim._2d.adapter.qt_viewer import DxfViewerSession
    from infobim._2d.plugin.capability.loader.annotation_details import (
        DxfAnnotationDetailsCapability,
    )

    session = DxfViewerSession(
        {"original": ezdxf.new()}, (("original", "Original", "drawing"),)
    )
    from test.unit.annotation.support import context as make_context

    context = make_context(tmp_path)
    context.set_parameter_value("dxf_viewer_session", session)
    session.show()
    timer = QtCore.QTimer()

    def cancel():
        for widget in qapp.allWidgets():
            if isinstance(widget, AnnotationDetailsForm) and widget.isVisible():
                widget.reject()

    timer.timeout.connect(cancel)
    timer.start(20)
    try:
        with pytest.raises(RuntimeError, match="cancelled"):
            DxfAnnotationDetailsCapability().execute(context)
        assert not session._dialog.isVisible()
    finally:
        timer.stop()
        import shiboken6

        if shiboken6.isValid(session._dialog):
            session.close()
