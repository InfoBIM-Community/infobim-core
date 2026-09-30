from typing import Any, ClassVar, Dict, List, Tuple
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QSurfaceFormat, QVector3D
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QUrl, Slot
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuick3D import QQuick3D

from infobim._3d.adapter.quick3d import IfcElementGeometry


class IfcPickRecorder(QObject):
    """Record the GlobalId of every IFC element picked in the scene."""

    def __init__(self) -> None:
        super().__init__()
        self._picked_global_ids: List[str] = []

    @Slot(str)
    def record(self, global_id: str) -> None:
        self._picked_global_ids.append(global_id)

    @property
    def picked_global_ids(self) -> List[str]:
        return list(self._picked_global_ids)


class IfcQuick3DViewer:
    """
    Show IFC element geometries in a navigable Qt Quick 3D scene.

    Every geometry becomes its own pickable Model, framed on start by the
    bounds of the whole set. The camera orbits, pans and zooms through
    Qt Quick 3D's OrbitCameraController, and a tap picks the element
    under the pointer.
    """

    SCENE_FILE: ClassVar[Path] = Path(__file__).with_name("ifc_viewer.qml")

    def __init__(self) -> None:
        # Qt Quick 3D bootstrap order: application, surface format, engine.
        self._application: QCoreApplication = (
            QGuiApplication.instance() or QGuiApplication([])
        )
        QSurfaceFormat.setDefaultFormat(QQuick3D.idealSurfaceFormat())
        self._picker: IfcPickRecorder = IfcPickRecorder()
        self._engine: QQmlApplicationEngine = QQmlApplicationEngine()
        self._geometries: List[IfcElementGeometry] = []

    @property
    def picked_global_ids(self) -> List[str]:
        return self._picker.picked_global_ids

    def open(self, geometries: List[IfcElementGeometry]) -> QQuickWindow:
        """Load the scene with ``geometries`` and return its window."""
        if not geometries:
            raise ValueError("There is no IFC element geometry to show.")

        # The scene only references the geometries; keep them alive with it.
        self._geometries = list(geometries)
        center: QVector3D
        radius: float
        center, radius = self._frame(self._geometries)
        properties: Dict[str, Any] = {
            "geometries": self._geometries,
            "sceneCenter": center,
            "sceneRadius": radius,
            "picker": self._picker,
        }
        self._engine.setInitialProperties(properties)
        self._engine.load(QUrl.fromLocalFile(str(self.SCENE_FILE)))
        roots: List[QObject] = self._engine.rootObjects()
        if len(roots) != 1 or not isinstance(roots[0], QQuickWindow):
            raise RuntimeError(f"The IFC 3D viewer scene failed to load: {self.SCENE_FILE}")

        return roots[0]

    def show(self, geometries: List[IfcElementGeometry]) -> List[str]:
        """Open the viewer, wait until its window closes and return the picks."""
        window: QQuickWindow = self.open(geometries)
        loop: QEventLoop = QEventLoop()
        window.closing.connect(loop.quit)
        loop.exec()
        self._application.processEvents()
        return self.picked_global_ids

    @staticmethod
    def _frame(geometries: List[IfcElementGeometry]) -> Tuple[QVector3D, float]:
        """
        Return the scene center, in Qt's Y-up frame, and the bounding radius.

        IFC is Z-up and the scene turns it -90 degrees about X, which maps an
        IFC point (x, y, z) to (x, z, -y).
        """
        minimum: QVector3D = QVector3D(geometries[0].boundsMin())
        maximum: QVector3D = QVector3D(geometries[0].boundsMax())
        geometry: IfcElementGeometry
        for geometry in geometries[1:]:
            low: QVector3D = geometry.boundsMin()
            high: QVector3D = geometry.boundsMax()
            minimum = QVector3D(
                min(minimum.x(), low.x()),
                min(minimum.y(), low.y()),
                min(minimum.z(), low.z()),
            )
            maximum = QVector3D(
                max(maximum.x(), high.x()),
                max(maximum.y(), high.y()),
                max(maximum.z(), high.z()),
            )

        center: QVector3D = (minimum + maximum) / 2
        radius: float = max((maximum - minimum).length() / 2, 1.0)
        return QVector3D(center.x(), center.z(), -center.y()), radius
