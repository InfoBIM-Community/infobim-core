from typing import Any, Callable, ClassVar, Dict, List, Mapping, Optional, Tuple

from ezdxf.document import Drawing
from ezdxf.addons.xqt import QtGui as qg
from ezdxf.addons.xqt import QtCore as qc
from ezdxf.addons.xqt import QtWidgets as qw
from ezdxf.addons.drawing.qtviewer import CADWidget, CADGraphicsView

from infobim._2d.adapter.annotation_details_form import AnnotationDetailsForm
from infobim._2d.domain.port.viewer import DxfViewerSessionPort


class PointCaptureView(CADGraphicsView):
    """
    CAD view that hands left clicks, left double clicks and the Backspace
    and Delete keys to a bound point capture. Without a bound capture it
    behaves exactly as ``CADGraphicsView``, including pan and zoom.
    """

    def __init__(self) -> None:
        super().__init__()
        self._capture: Optional["DxfPointCapture"] = None
        self._press_position: Optional[qc.QPoint] = None

    def bind_capture(self, capture: Optional["DxfPointCapture"]) -> None:
        self._capture = capture
        self._press_position = None

    def mousePressEvent(self, event: qg.QMouseEvent) -> None:
        if self._capture is not None and event.button() == qc.Qt.MouseButton.LeftButton:
            self._press_position = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: qg.QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if (
            self._capture is None
            or event.button() != qc.Qt.MouseButton.LeftButton
            or self._press_position is None
        ):
            return

        moved: int = (event.pos() - self._press_position).manhattanLength()
        self._press_position = None
        # A drag pans the drawing; only a click without movement picks a point.
        if moved < qw.QApplication.startDragDistance():
            self._capture.click(self.mapToScene(event.pos()))

    def mouseDoubleClickEvent(self, event: qg.QMouseEvent) -> None:
        if self._capture is not None and event.button() == qc.Qt.MouseButton.LeftButton:
            self._press_position = None
            self._capture.finish(self.mapToScene(event.pos()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: qg.QKeyEvent) -> None:
        if self._capture is not None and event.key() in (
            qc.Qt.Key.Key_Backspace,
            qc.Qt.Key.Key_Delete,
        ):
            self._capture.remove_last()
            event.accept()
            return
        super().keyPressEvent(event)


class DxfPointCapture:
    """
    Collect the points picked on a view, in click order, and mark each one
    with a cyan disc labelled with its coordinates.

    A click is held for the double-click interval before it becomes a
    point: the first click of a double click is then discarded, since the
    double click itself adds the last point and finishes the capture. The
    markers are overlay items of the view's scene; the drawing itself is
    never changed.
    """

    MARKER_RADIUS: ClassVar[float] = 6.0
    MARKER_COLOR: ClassVar[Tuple[int, int, int]] = (0, 255, 255)
    LABEL_GAP: ClassVar[float] = 3.0
    MARKER_Z_VALUE: ClassVar[float] = 1_000_000.0

    def __init__(self, view: PointCaptureView, on_finished: Callable[[], None]) -> None:
        self._view: PointCaptureView = view
        self._on_finished: Callable[[], None] = on_finished
        self._points: List[qc.QPointF] = []
        self._markers: List[qw.QGraphicsEllipseItem] = []
        self._pending: Optional[qc.QPointF] = None
        self._finished: bool = False
        self._timer: qc.QTimer = qc.QTimer(view)
        self._timer.setSingleShot(True)
        self._timer.setInterval(qw.QApplication.doubleClickInterval())
        self._timer.timeout.connect(self._commit_pending)

    @property
    def finished(self) -> bool:
        return self._finished

    def points(self) -> List[Dict[str, float]]:
        return [{"x": float(point.x()), "y": float(point.y())} for point in self._points]

    def click(self, point: qc.QPointF) -> None:
        self._commit_pending()
        self._pending = qc.QPointF(point)
        self._timer.start()

    def remove_last(self) -> None:
        self._commit_pending()
        if not self._points:
            return
        self._points.pop()
        marker: qw.QGraphicsEllipseItem = self._markers.pop()
        if marker.scene() is not None:
            marker.scene().removeItem(marker)

    def finish(self, point: qc.QPointF) -> None:
        self._timer.stop()
        self._pending = None
        self._add(qc.QPointF(point))
        self._finished = True
        self._on_finished()

    def redraw(self) -> None:
        """Put the markers back after the view received a new scene."""
        self._markers = [self._marker(point) for point in self._points]

    def detach(self) -> None:
        self._timer.stop()
        marker: qw.QGraphicsEllipseItem
        for marker in self._markers:
            if marker.scene() is not None:
                marker.scene().removeItem(marker)
        self._markers = []

    def _commit_pending(self) -> None:
        self._timer.stop()
        if self._pending is None:
            return
        point: qc.QPointF = self._pending
        self._pending = None
        self._add(point)

    def _add(self, point: qc.QPointF) -> None:
        self._points.append(point)
        self._markers.append(self._marker(point))

    def _marker(self, point: qc.QPointF) -> qw.QGraphicsEllipseItem:
        color: qg.QColor = qg.QColor(*self.MARKER_COLOR)
        radius: float = self.MARKER_RADIUS
        disc: qw.QGraphicsEllipseItem = qw.QGraphicsEllipseItem(
            -radius, -radius, 2 * radius, 2 * radius
        )
        disc.setBrush(qg.QBrush(color))
        disc.setPen(qg.QPen(qc.Qt.PenStyle.NoPen))
        # Constant screen size and upright text whatever the pan and zoom.
        disc.setFlag(qw.QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        disc.setZValue(self.MARKER_Z_VALUE)
        disc.setPos(point)

        label: qw.QGraphicsSimpleTextItem = qw.QGraphicsSimpleTextItem(
            f"({point.x():.1f}, {point.y():.1f})", disc
        )
        label.setBrush(qg.QBrush(color))
        label.setPos(
            radius + self.LABEL_GAP,
            -radius - self.LABEL_GAP - label.boundingRect().height(),
        )

        self._view.scene().addItem(disc)
        return disc


class DxfViewerSession(DxfViewerSessionPort):
    """One window of the InfoBIM 2D viewer with a tab per drawing state."""

    WINDOW_TITLE: ClassVar[str] = "InfoBIM 2D Viewer"

    def __init__(
        self,
        documents: Mapping[str, Drawing],
        states: Tuple[Tuple[str, str, str], ...],
    ) -> None:
        application: Any = qw.QApplication.instance()
        self._owns_application: bool = application is None
        if application is None:
            application = qw.QApplication([])
        self._application: Any = application
        self._documents: Mapping[str, Drawing] = documents
        self._loaded_callbacks: List[Callable[[], None]] = []

        self._dialog: qw.QDialog = qw.QDialog()
        self._dialog.setWindowTitle(self.WINDOW_TITLE)
        self._dialog.resize(1200, 800)

        layout: qw.QVBoxLayout = qw.QVBoxLayout(self._dialog)

        tabs: qw.QTabBar = qw.QTabBar()
        tabs.setExpanding(False)
        layout.addWidget(tabs)

        self._view: PointCaptureView = PointCaptureView()
        self._view.setFocusPolicy(qc.Qt.FocusPolicy.StrongFocus)
        self._cad: CADWidget = CADWidget(self._view)

        self._loading_widget: qw.QWidget = qw.QWidget()
        loading_layout: qw.QVBoxLayout = qw.QVBoxLayout(self._loading_widget)
        loading_layout.addStretch(1)

        loading_label: qw.QLabel = qw.QLabel("Loading drawing…")
        loading_layout.addWidget(loading_label)

        loading_bar: qw.QProgressBar = qw.QProgressBar()
        loading_bar.setRange(0, 0)
        loading_bar.setTextVisible(False)
        loading_layout.addWidget(loading_bar)
        loading_layout.addStretch(1)

        self._stack: qw.QStackedWidget = qw.QStackedWidget()
        self._stack.addWidget(self._loading_widget)
        self._stack.addWidget(self._cad)
        layout.addWidget(self._stack)

        self._states: List[str] = []
        state: str
        label: str
        for state, label, _key in states:
            if state not in documents:
                continue
            tabs.addTab(label)
            self._states.append(state)

        self._current_state: str = self._states[0]
        tabs.currentChanged.connect(self._load)
        self._load(0)

    @property
    def current_state(self) -> str:
        return self._current_state

    def show(self) -> None:
        self._dialog.show()
        self._application.processEvents()

    def run(self) -> str:
        self._execute_dialog()
        return self._current_state

    def capture_points(self) -> List[Dict[str, float]]:
        capture: DxfPointCapture = DxfPointCapture(self._view, self._dialog.accept)
        self._view.bind_capture(capture)
        self._loaded_callbacks.append(capture.redraw)
        self._view.setFocus()
        try:
            self._execute_dialog()
        finally:
            self._loaded_callbacks.remove(capture.redraw)
            self._view.bind_capture(None)
            capture.detach()

        if not capture.finished:
            raise RuntimeError(
                "Point capture was closed before a double click finished it."
            )
        return capture.points()

    def request_annotation_details(self) -> Dict[str, str]:
        form: AnnotationDetailsForm = AnnotationDetailsForm(self._dialog)
        execute_form: Any = getattr(form, "exec", None) or getattr(form, "exec_")
        accepted: bool = bool(execute_form())
        details: Dict[str, str] = form.details()
        form.deleteLater()
        if not accepted:
            raise RuntimeError("The annotation details form was cancelled.")
        return details

    def close(self) -> None:
        self._dialog.close()
        self._dialog.deleteLater()
        if self._owns_application:
            self._application.processEvents()

    def _load(self, index: int) -> None:
        state_name: str = self._states[index]
        self._current_state = state_name
        self._stack.setCurrentWidget(self._loading_widget)
        self._application.processEvents()
        try:
            self._cad.set_document(self._documents[state_name], layout="Model")
        finally:
            self._stack.setCurrentWidget(self._cad)
            self._application.processEvents()
        callback: Callable[[], None]
        for callback in self._loaded_callbacks:
            callback()

    def _execute_dialog(self) -> None:
        execute_dialog: Any = getattr(self._dialog, "exec", None) or getattr(
            self._dialog, "exec_"
        )
        execute_dialog()
