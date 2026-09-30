from typing import Any, Dict, List, Optional, Sequence, Tuple
from pathlib import Path
from importlib import import_module

import ezdxf
from ezdxf.document import Drawing
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.context.adapter.taxonomy import CAPABILITY_PREFIX, MACHINE_PACKAGE, VECTOR_TRACE_KEY
from infobim.context.adapter.kind_resolution_event import KindResolutionEvent

DxfVectorProcessState: Any = import_module(MACHINE_PACKAGE + ".state").DxfVectorProcessState


Point2D = Tuple[float, float]


class _VectorCapability(TransactionCapability):
    @staticmethod
    def _metadata(state_name: str, description: str) -> CapabilityMetadata:
        return CapabilityMetadata(
            id=CAPABILITY_PREFIX + state_name,
            version="1.0.0",
            name=f"DXF vector: {state_name.replace('_', ' ')}",
            description=description,
            author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
            tags=["infobim", "drawing", "dxf", "2d", "vector", "fsm"],
            supported_languages=["en", "pt-br"],
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
        )

    def label(self, lang: str = "en") -> str:
        return self.METADATA.name

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description


class DxfVectorLoadedCapability(_VectorCapability):
    METADATA = _VectorCapability._metadata(
        "dxf_loaded",
        "Load the DXF document used as the interactive vector background.",
    )

    OUTPUT_KEY: str = "vector_dxf_loaded"

    def is_satisfied(self, context: CliContextPort) -> bool:
        event: Optional[Dict[str, Any]] = KindResolutionEvent.read(
            context, DxfVectorProcessState.DXF_LOADED.value, self.METADATA.version, self.OUTPUT_KEY
        )
        if event is None:
            context.delete_parameter("vector_dxf_document")
            return False
        # The parsed ezdxf Drawing cannot be persisted as JSON, so a
        # satisfied event still re-reads the source into context here.
        context.set_parameter_value(
            "vector_dxf_document", self._read_document(context)
        )
        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document: Drawing = self._read_document(context)
        context.set_parameter_value("vector_dxf_document", document)
        output: Dict[str, Any] = {self.OUTPUT_KEY: True}
        KindResolutionEvent.write(
            context, DxfVectorProcessState.DXF_LOADED.value, self.METADATA.version, output
        )
        return output

    @staticmethod
    def _read_document(context: CliContextPort) -> Drawing:
        source: Path = Path(str(context.get_parameter_value("dxf_path"))).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() != ".dxf":
            raise CliCommandArgumentException(f"Not a DXF file: {source}")
        try:
            return ezdxf.readfile(source)
        except (IOError, ezdxf.DXFError) as error:
            raise CliCommandArgumentException(
                f"Could not read DXF file: {source}: {error}"
            ) from error


class DxfVectorCapturedCapability(_VectorCapability):
    METADATA = _VectorCapability._metadata(
        "vector_captured",
        "Capture a polyline made of straight segments between successive clicks.",
    )

    OUTPUT_KEY: str = VECTOR_TRACE_KEY

    def is_satisfied(self, context: CliContextPort) -> bool:
        event: Optional[Dict[str, Any]] = KindResolutionEvent.read(
            context, DxfVectorProcessState.VECTOR_CAPTURED.value, self.METADATA.version, self.OUTPUT_KEY
        )
        if event is None:
            context.delete_parameter("vector_trace")
            return False
        points: Any = event["output"][self.OUTPUT_KEY]
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError(f"ETL output {self.OUTPUT_KEY} must hold at least two points.")
        context.set_parameter_value(
            "vector_trace", [(float(point[0]), float(point[1])) for point in points]
        )
        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document = context.get_parameter_value("vector_dxf_document")
        if not isinstance(document, Drawing):
            raise CliCommandArgumentException(
                "The DXF document is not loaded for vector capture."
            )
        source = Path(str(context.get_parameter_value("dxf_path"))).expanduser().resolve()
        points: List[Point2D] = self._capture_vector(document, source.name)
        context.set_parameter_value("vector_trace", points)
        output: Dict[str, Any] = {
            self.OUTPUT_KEY: [[point[0], point[1]] for point in points],
        }
        KindResolutionEvent.write(
            context, DxfVectorProcessState.VECTOR_CAPTURED.value, self.METADATA.version, output
        )
        return output

    @staticmethod
    def _capture_vector(document: Drawing, file_name: str) -> List[Point2D]:
        try:
            from ezdxf.addons.xqt import QtCore as qc
            from ezdxf.addons.xqt import QtGui as qg
            from ezdxf.addons.xqt import QtWidgets as qw
            from ezdxf.addons.xqt import Signal
            from ezdxf.addons.drawing.qtviewer import CADGraphicsView, CADWidget
        except ImportError as error:
            raise RuntimeError(
                "InfoBIM 2D vector capture requires PySide6 (or PyQt5). "
                "Reinstall InfoBIM with its current dependencies."
            ) from error

        class VectorCaptureView(CADGraphicsView):
            vector_finished = Signal(object)

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self._points: List[Point2D] = []
                self._path = None
                self._path_item = None
                self._preview_item = None
                self.setMouseTracking(True)
                self.viewport().setMouseTracking(True)
                self.setFocusPolicy(qc.Qt.StrongFocus)
                self._set_marking_mode()

            def _pen(self) -> Any:
                pen = qg.QPen(self.palette().highlight().color())
                pen.setCosmetic(True)
                pen.setWidth(2)
                return pen

            def _set_marking_mode(self) -> None:
                """Left click marks a point. This is the default mode."""
                self.setDragMode(qw.QGraphicsView.NoDrag)
                self.viewport().setCursor(qc.Qt.CrossCursor)

            def _set_panning_mode(self) -> None:
                """Left click drags the view. Active only while Shift is held."""
                self.setDragMode(qw.QGraphicsView.ScrollHandDrag)
                self.viewport().setCursor(qc.Qt.OpenHandCursor)

            def _is_panning(self, event: Any) -> bool:
                return bool(event.modifiers() & qc.Qt.ShiftModifier)

            def keyPressEvent(self, event: qg.QKeyEvent) -> None:
                if event.key() == qc.Qt.Key_Shift:
                    self._set_panning_mode()
                    event.accept()
                    return
                super().keyPressEvent(event)

            def keyReleaseEvent(self, event: qg.QKeyEvent) -> None:
                if event.key() == qc.Qt.Key_Shift:
                    self._set_marking_mode()
                    event.accept()
                    return
                super().keyReleaseEvent(event)

            def mousePressEvent(self, event: qg.QMouseEvent) -> None:
                if event.button() == qc.Qt.LeftButton and not self._is_panning(event):
                    scene_point = self.mapToScene(event.pos())
                    self._append_point(scene_point)
                    event.accept()
                    return
                super().mousePressEvent(event)

            def mouseMoveEvent(self, event: qg.QMouseEvent) -> None:
                if self._points and not self._is_panning(event):
                    scene_point = self.mapToScene(event.pos())
                    start = self._points[-1]
                    if self._preview_item is None:
                        self._preview_item = self.scene().addLine(
                            start[0], start[1], scene_point.x(), scene_point.y(), self._pen()
                        )
                    else:
                        self._preview_item.setLine(
                            start[0], start[1], scene_point.x(), scene_point.y()
                        )
                super().mouseMoveEvent(event)

            def mouseDoubleClickEvent(self, event: qg.QMouseEvent) -> None:
                if event.button() == qc.Qt.LeftButton and not self._is_panning(event):
                    scene_point = self.mapToScene(event.pos())
                    self._append_point(scene_point)
                    if len(self._points) >= 2:
                        self._remove_preview()
                        self.vector_finished.emit(list(self._points))
                    event.accept()
                    return
                super().mouseDoubleClickEvent(event)

            def _append_point(self, scene_point: Any) -> None:
                point = (float(scene_point.x()), float(scene_point.y()))
                if self._points and self._same_point(self._points[-1], point):
                    return
                self._points.append(point)
                if self._path is None:
                    self._path = qg.QPainterPath(scene_point)
                    self._path_item = self.scene().addPath(self._path, self._pen())
                else:
                    self._path.lineTo(scene_point)
                    if self._path_item is not None:
                        self._path_item.setPath(self._path)
                self._remove_preview()

            def _remove_preview(self) -> None:
                if self._preview_item is not None and self.scene() is not None:
                    self.scene().removeItem(self._preview_item)
                self._preview_item = None

            @staticmethod
            def _same_point(first: Point2D, second: Point2D, tolerance: float = 1e-12) -> bool:
                return (
                    abs(first[0] - second[0]) <= tolerance
                    and abs(first[1] - second[1]) <= tolerance
                )

        application = qw.QApplication.instance()
        owns_application = application is None
        if application is None:
            application = qw.QApplication([])

        dialog = qw.QDialog()
        dialog.setWindowTitle(f"InfoBIM 2D Vector — {file_name}")
        dialog.resize(1200, 800)
        layout = qw.QVBoxLayout(dialog)
        layout.addWidget(
            qw.QLabel(
                "Click to add vertices. Each click creates a straight segment from "
                "the previous point. Double-click to finish. Hold Shift to pan the "
                "view instead. Close to cancel."
            )
        )
        view = VectorCaptureView()
        cad = CADWidget(view)
        layout.addWidget(cad)
        view.setFocus()

        selected: List[List[Point2D]] = []

        def on_vector(points: Sequence[Point2D]) -> None:
            selected.append([(float(x), float(y)) for x, y in points])
            dialog.accept()

        view.vector_finished.connect(on_vector)
        cad.set_document(document, layout="Model")
        execute_dialog = getattr(dialog, "exec", None) or getattr(dialog, "exec_")
        execute_dialog()
        dialog.deleteLater()
        if owns_application:
            application.processEvents()
        if not selected:
            raise CliCommandArgumentException("Vector capture cancelled.")
        return selected[0]


class DxfVectorTraceReadyCapability(_VectorCapability):
    METADATA = _VectorCapability._metadata(
        "trace_ready",
        "Serialize the captured straight-segment trace for direct reuse.",
    )

    OUTPUT_KEY: str = "vector_trace_text"

    def is_satisfied(self, context: CliContextPort) -> bool:
        event: Optional[Dict[str, Any]] = KindResolutionEvent.read(
            context, DxfVectorProcessState.TRACE_READY.value, self.METADATA.version, self.OUTPUT_KEY
        )
        if event is None:
            context.delete_parameter("vector_trace_text")
            return False
        trace_text: Any = event["output"][self.OUTPUT_KEY]
        if not isinstance(trace_text, str) or not trace_text.strip():
            raise ValueError(f"ETL output {self.OUTPUT_KEY} must be a non-empty string.")
        context.set_parameter_value("vector_trace_text", trace_text)
        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw_points = context.get_parameter_value("vector_trace")
        if not isinstance(raw_points, list) or len(raw_points) < 2:
            raise CliCommandArgumentException("No captured vector trace is available.")
        points: List[Point2D] = []
        for raw in raw_points:
            if not isinstance(raw, (list, tuple)) or len(raw) != 2:
                raise CliCommandArgumentException(
                    "The captured vector trace contains an invalid point."
                )
            points.append((float(raw[0]), float(raw[1])))
        trace_text = ";".join(
            f"{self._format_coordinate(x)},{self._format_coordinate(y)}"
            for x, y in points
        )
        context.set_parameter_value("vector_trace_text", trace_text)
        output: Dict[str, Any] = {self.OUTPUT_KEY: trace_text}
        KindResolutionEvent.write(
            context, DxfVectorProcessState.TRACE_READY.value, self.METADATA.version, output
        )
        return output

    @staticmethod
    def _format_coordinate(value: float) -> str:
        if abs(value) < 1e-12:
            value = 0.0
        return format(value, ".15g")
