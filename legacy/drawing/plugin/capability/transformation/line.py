from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import ezdxf
from ezdxf.document import Drawing
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


Point2D = Tuple[float, float]


class _LineCapability(TransactionCapability):
    @staticmethod
    def _metadata(state_name: str, description: str) -> CapabilityMetadata:
        return CapabilityMetadata(
            id=(
                "org.infobim.drawing.plugin.capability.transformation."
                f"line.target.{state_name}"
            ),
            version="1.0.0",
            name=f"DXF line: {state_name.replace('_', ' ')}",
            description=description,
            author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
            tags=["infobim", "drawing", "dxf", "2d", "line", "fsm"],
            supported_languages=["en", "pt-br"],
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
        )

    def label(self, lang: str = "en") -> str:
        return self.METADATA.name

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description


class DxfLineLoadedCapability(_LineCapability):
    METADATA = _LineCapability._metadata(
        "dxf_loaded",
        "Load the DXF document used as the interactive drawing background.",
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        source = Path(
            str(context.get_parameter_value("dxf_path"))
        ).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() != ".dxf":
            raise CliCommandArgumentException(f"Not a DXF file: {source}")

        try:
            document: Drawing = ezdxf.readfile(source)
        except (IOError, ezdxf.DXFError) as error:
            raise CliCommandArgumentException(
                f"Could not read DXF file: {source}: {error}"
            ) from error

        context.set_parameter_value("line_dxf_document", document)
        return {
            "line_dxf_loaded": True,
            "line_source": str(source),
        }


class DxfLineCapturedCapability(_LineCapability):
    METADATA = _LineCapability._metadata(
        "line_captured",
        "Capture a freehand line over the rendered DXF in modelspace coordinates.",
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document = context.get_parameter_value("line_dxf_document")
        if not isinstance(document, Drawing):
            raise CliCommandArgumentException(
                "The DXF document is not loaded for line capture."
            )

        source = Path(
            str(context.get_parameter_value("dxf_path"))
        ).expanduser().resolve()
        points = self._capture_line(document, source.name)
        context.set_parameter_value("line_trace", points)

        return {"line_point_count": len(points)}

    @staticmethod
    def _capture_line(document: Drawing, file_name: str) -> List[Point2D]:
        try:
            from ezdxf.addons.xqt import QtCore as qc
            from ezdxf.addons.xqt import QtGui as qg
            from ezdxf.addons.xqt import QtWidgets as qw
            from ezdxf.addons.xqt import Signal
            from ezdxf.addons.drawing.qtviewer import CADGraphicsView, CADWidget
        except ImportError as error:
            raise RuntimeError(
                "InfoBIM 2D line capture requires PySide6 (or PyQt5). "
                "Reinstall InfoBIM with its current dependencies."
            ) from error

        class LineCaptureView(CADGraphicsView):
            line_finished = Signal(object)

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self._drawing = False
                self._points: List[Point2D] = []
                self._path = None
                self._path_item = None

            def mousePressEvent(self, event: qg.QMouseEvent) -> None:
                if event.button() == qc.Qt.LeftButton:
                    scene_point = self.mapToScene(event.pos())
                    self._drawing = True
                    self._points = [
                        (float(scene_point.x()), float(scene_point.y()))
                    ]
                    self._path = qg.QPainterPath(scene_point)

                    pen = qg.QPen(self.palette().highlight().color())
                    pen.setCosmetic(True)
                    pen.setWidth(2)
                    self._path_item = self.scene().addPath(self._path, pen)

                    event.accept()
                    return
                super().mousePressEvent(event)

            def mouseMoveEvent(self, event: qg.QMouseEvent) -> None:
                if self._drawing and event.buttons() & qc.Qt.LeftButton:
                    scene_point = self.mapToScene(event.pos())
                    point = (float(scene_point.x()), float(scene_point.y()))
                    if not self._points or not self._same_point(
                        self._points[-1], point
                    ):
                        self._points.append(point)
                        self._path.lineTo(scene_point)
                        if self._path_item is not None:
                            self._path_item.setPath(self._path)

                    event.accept()
                    return
                super().mouseMoveEvent(event)

            def mouseReleaseEvent(self, event: qg.QMouseEvent) -> None:
                if self._drawing and event.button() == qc.Qt.LeftButton:
                    scene_point = self.mapToScene(event.pos())
                    point = (float(scene_point.x()), float(scene_point.y()))
                    if not self._points or not self._same_point(
                        self._points[-1], point
                    ):
                        self._points.append(point)
                        self._path.lineTo(scene_point)
                        if self._path_item is not None:
                            self._path_item.setPath(self._path)

                    self._drawing = False
                    if len(self._points) >= 2:
                        self.line_finished.emit(list(self._points))
                    else:
                        self._reset_trace()

                    event.accept()
                    return
                super().mouseReleaseEvent(event)

            def _reset_trace(self) -> None:
                if self._path_item is not None and self.scene() is not None:
                    self.scene().removeItem(self._path_item)
                self._points = []
                self._path = None
                self._path_item = None

            @staticmethod
            def _same_point(
                first: Point2D,
                second: Point2D,
                tolerance: float = 1e-12,
            ) -> bool:
                return (
                    abs(first[0] - second[0]) <= tolerance
                    and abs(first[1] - second[1]) <= tolerance
                )

        application = qw.QApplication.instance()
        owns_application = application is None
        if application is None:
            application = qw.QApplication([])

        dialog = qw.QDialog()
        dialog.setWindowTitle(f"InfoBIM 2D Line — {file_name}")
        dialog.resize(1200, 800)

        layout = qw.QVBoxLayout(dialog)
        hint = qw.QLabel(
            "Press and hold the left mouse button to draw. "
            "Release to capture the trace. Close the window to cancel."
        )
        layout.addWidget(hint)

        view = LineCaptureView()
        cad = CADWidget(view)
        layout.addWidget(cad)

        selected: List[List[Point2D]] = []

        def on_line(points: Sequence[Point2D]) -> None:
            selected.append(
                [(float(point[0]), float(point[1])) for point in points]
            )
            dialog.accept()

        view.line_finished.connect(on_line)
        cad.set_document(document, layout="Model")

        execute_dialog = getattr(dialog, "exec", None) or getattr(dialog, "exec_")
        execute_dialog()
        dialog.deleteLater()

        if owns_application:
            application.processEvents()

        if not selected:
            raise CliCommandArgumentException("Line capture cancelled.")

        return selected[0]


class DxfLineTraceReadyCapability(_LineCapability):
    METADATA = _LineCapability._metadata(
        "trace_ready",
        "Serialize the captured modelspace trace for direct reuse.",
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw_points = context.get_parameter_value("line_trace")
        if not isinstance(raw_points, list) or len(raw_points) < 2:
            raise CliCommandArgumentException(
                "No captured line trace is available."
            )

        points: List[Point2D] = []
        for raw in raw_points:
            if not isinstance(raw, (list, tuple)) or len(raw) != 2:
                raise CliCommandArgumentException(
                    "The captured line trace contains an invalid point."
                )
            points.append((float(raw[0]), float(raw[1])))

        trace_text = ";".join(
            f"{self._format_coordinate(x)},{self._format_coordinate(y)}"
            for x, y in points
        )
        context.set_parameter_value("line_trace_text", trace_text)

        return {
            "line_trace_text": trace_text,
            "line_point_count": len(points),
        }

    @staticmethod
    def _format_coordinate(value: float) -> str:
        if abs(value) < 1e-12:
            value = 0.0
        return format(value, ".15g")
