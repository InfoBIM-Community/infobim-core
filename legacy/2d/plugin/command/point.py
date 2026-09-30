from pathlib import Path
from typing import Any, ClassVar, List, Tuple

import ezdxf
from ezdxf.document import Drawing
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class DxfPointCommand(CliCommandPort):
    """Open a DXF viewer and return the coordinates of a double-clicked point."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_point",
        logical_component="2d",
        description="Pick a point in a DXF drawing and return its X/Y coordinates.",
        interactive=True,
        arguments=[
            {
                "accepts": ["--point"],
                "valued": True,
                "parameter": "dxf_path",
                "description": "Path to the DXF file used for point selection.",
                "usage": "infobim 2d --point <path/to/file.dxf>",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "2d"
    FLAG: ClassVar[str] = "--point"
    DXF_PATH_KEY: ClassVar[str] = "dxf_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 3
            and args[0] == DxfPointCommand.COMPONENT
            and args[1] == DxfPointCommand.FLAG
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        if not (
            len(command_args) == 2
            and command_args[0] == self.FLAG
            and bool(str(command_args[1]).strip())
        ):
            return False

        source_path: Path = Path(command_args[1]).expanduser().resolve()
        if not source_path.is_file():
            raise CliCommandArgumentException(f"DXF file not found: {source_path}")
        if source_path.suffix.lower() != ".dxf":
            raise CliCommandArgumentException(f"Not a DXF file: {source_path}")

        self._request.context.set_parameter_value(
            self.DXF_PATH_KEY,
            str(source_path),
        )
        return True

    def run(self) -> CommandResponse:
        source_value: Any = self._request.context.get_parameter_value(
            self.DXF_PATH_KEY
        )
        if not isinstance(source_value, str) or not source_value.strip():
            raise CliCommandArgumentException("Required parameter is missing: dxf_path")

        source_path: Path = Path(source_value).expanduser().resolve()
        try:
            document: Drawing = ezdxf.readfile(source_path)
        except (IOError, ezdxf.DXFError) as error:
            raise CliCommandArgumentException(
                f"Could not read DXF file: {source_path}: {error}"
            ) from error

        x, y = self._capture_point(document, source_path.name)
        x_text: str = self._format_coordinate(x)
        y_text: str = self._format_coordinate(y)
        arguments: str = f"--x {x_text} --y {y_text}"

        return CommandResponse(
            title="InfoBIM 2D: Point",
            description="Captured the double-clicked DXF modelspace coordinate.",
            content={"arguments": arguments},
        )

    @staticmethod
    def _capture_point(document: Drawing, file_name: str) -> Tuple[float, float]:
        """Show the ezdxf Qt viewer and block until a point is chosen or cancelled."""
        try:
            from ezdxf.addons.xqt import QtCore as qc
            from ezdxf.addons.xqt import QtGui as qg
            from ezdxf.addons.xqt import QtWidgets as qw
            from ezdxf.addons.xqt import Signal
            from ezdxf.addons.drawing.qtviewer import CADGraphicsView, CADWidget
        except ImportError as error:
            raise RuntimeError(
                "InfoBIM 2D point selection requires PySide6 (or PyQt5). "
                "Reinstall InfoBIM with its current dependencies."
            ) from error

        class PointCaptureView(CADGraphicsView):
            point_selected = Signal(qc.QPointF)

            def mouseDoubleClickEvent(self, event: qg.QMouseEvent) -> None:
                if event.button() == qc.Qt.LeftButton:
                    self.point_selected.emit(self.mapToScene(event.pos()))
                    event.accept()
                    return
                super().mouseDoubleClickEvent(event)

            def wheelEvent(self, event: qg.QWheelEvent) -> None:
                """Zoom under the cursor for both wheel and touchpad events."""
                angle_delta = float(event.angleDelta().y())
                pixel_delta = float(event.pixelDelta().y())

                if angle_delta:
                    factor = 1.2 ** (angle_delta / 120.0)
                elif pixel_delta:
                    # Precision touchpads may report only pixelDelta().
                    factor = 1.002 ** pixel_delta
                else:
                    super().wheelEvent(event)
                    return

                resulting_zoom = self._zoom * factor
                minimum_zoom, maximum_zoom = self._zoom_limits
                if resulting_zoom < minimum_zoom:
                    factor = minimum_zoom / self._zoom
                elif resulting_zoom > maximum_zoom:
                    factor = maximum_zoom / self._zoom

                self.scale(factor, factor)
                self._zoom *= factor
                event.accept()

        application = qw.QApplication.instance()
        owns_application: bool = application is None
        if application is None:
            application = qw.QApplication([])

        dialog = qw.QDialog()
        dialog.setWindowTitle(f"InfoBIM 2D Point — {file_name}")
        dialog.resize(1200, 800)

        layout = qw.QVBoxLayout(dialog)
        hint = qw.QLabel("Double-click the point to capture. Close the window to cancel.")
        layout.addWidget(hint)

        view = PointCaptureView()
        view.setFocusPolicy(qc.Qt.StrongFocus)
        cad = CADWidget(view)
        layout.addWidget(cad)

        selected: List[Tuple[float, float]] = []

        def on_point(point: qc.QPointF) -> None:
            selected.append((float(point.x()), float(point.y())))
            dialog.accept()

        view.point_selected.connect(on_point)
        cad.set_document(document, layout="Model")
        view.setFocus()

        execute_dialog = getattr(dialog, "exec", None) or getattr(dialog, "exec_")
        execute_dialog()
        dialog.deleteLater()

        if owns_application:
            application.processEvents()

        if not selected:
            raise CliCommandArgumentException("Point selection cancelled.")

        return selected[0]

    @staticmethod
    def _format_coordinate(value: float) -> str:
        if abs(value) < 1e-12:
            value = 0.0
        return format(value, ".15g")
