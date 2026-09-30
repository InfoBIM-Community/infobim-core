"""Create simplified discipline DXF drawings from IFC geometry."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Any, ClassVar, Iterable, List, Optional, Sequence, Tuple

import ezdxf
from ezdxf.document import Drawing
from ezdxf.units import M


Point3 = Tuple[float, float, float]


@dataclass(frozen=True)
class IfcDrawingConversion:
    """Result of generating a discipline drawing from an IFC model."""

    source: str
    output: str
    discipline: str
    centerlines: int
    outlines: int
    skipped_geometry: int


class IfcPlumbingDxfConverter:
    """Project plumbing IFC geometry into a simple plan-view DXF."""

    DISCIPLINE: ClassVar[str] = "plumbing"
    LAYER_NAME: ClassVar[str] = "INFOBIM_PLUMBING"
    LINETYPE_NAME: ClassVar[str] = "INFOBIM_DASHED"
    BLUE_ACI: ClassVar[int] = 5
    PLAN_TOLERANCE: ClassVar[float] = 1.0e-6
    RISER_HALF_SIZE: ClassVar[float] = 0.05

    DIRECT_PLUMBING_TYPES: ClassVar[Tuple[str, ...]] = (
        "IfcPipeSegment",
        "IfcPipeFitting",
        "IfcSanitaryTerminal",
        "IfcWasteTerminal",
        "IfcInterceptor",
        "IfcValve",
        "IfcPump",
        "IfcTank",
        "IfcDistributionChamberElement",
    )
    SEMANTIC_DISTRIBUTION_TYPES: ClassVar[Tuple[str, ...]] = (
        "IfcFlowSegment",
        "IfcFlowFitting",
        "IfcFlowController",
        "IfcFlowMovingDevice",
        "IfcFlowStorageDevice",
        "IfcFlowTerminal",
        "IfcFlowInstrument",
    )
    PLUMBING_KEYWORDS: ClassVar[Tuple[str, ...]] = (
        "PIPE",
        "PLUMB",
        "WATER",
        "SANIT",
        "WASTE",
        "SEWER",
        "DRAIN",
        "ESGOTO",
        "HIDR",
        "AGUA",
        "ÁGUA",
        "VALVE",
        "VALV",
        "PUMP",
        "BOMBA",
        "SINK",
        "LAVATORY",
        "BASIN",
        "TOILET",
        "URINAL",
        "SHOWER",
        "CHUVEIRO",
    )

    @classmethod
    def convert(
        cls,
        source: Path,
        output: Optional[Path] = None,
    ) -> IfcDrawingConversion:
        """Write a blue dashed plumbing DXF beside ``source`` by default."""
        import ifcopenshell

        source = source.expanduser().resolve()
        target = (
            source.with_name(f"{source.stem}.{cls.DISCIPLINE}.dxf")
            if output is None
            else output.expanduser().resolve()
        )
        model: Any = ifcopenshell.open(str(source))
        drawing: Drawing = cls._new_drawing()
        modelspace: Any = drawing.modelspace()

        centerlines = 0
        outlines = 0
        skipped_geometry = 0

        for element, points in cls._shapes(model):
            if not cls._is_plumbing(element):
                continue
            if not points:
                skipped_geometry += 1
                continue

            if cls._is_pipe_like(element):
                start, end = cls._centerline(points)
                if cls._plan_distance(start, end) <= cls.PLAN_TOLERANCE:
                    cls._add_riser(modelspace, cls._centroid(points))
                else:
                    modelspace.add_line(
                        (start[0], start[1], 0.0),
                        (end[0], end[1], 0.0),
                        dxfattribs={"layer": cls.LAYER_NAME},
                    )
                centerlines += 1
                continue

            if cls._add_outline(modelspace, points):
                outlines += 1
            else:
                skipped_geometry += 1

        target.parent.mkdir(parents=True, exist_ok=True)
        drawing.saveas(target)
        return IfcDrawingConversion(
            source=str(source),
            output=str(target),
            discipline=cls.DISCIPLINE,
            centerlines=centerlines,
            outlines=outlines,
            skipped_geometry=skipped_geometry,
        )

    @classmethod
    def _new_drawing(cls) -> Drawing:
        drawing: Drawing = ezdxf.new("R2010")
        drawing.units = M
        drawing.header["$LTSCALE"] = 1.0
        if cls.LINETYPE_NAME not in drawing.linetypes:
            drawing.linetypes.add(
                cls.LINETYPE_NAME,
                pattern=[0.20, 0.10, -0.10],
                description="InfoBIM dashed",
            )
        drawing.layers.add(
            cls.LAYER_NAME,
            color=cls.BLUE_ACI,
            linetype=cls.LINETYPE_NAME,
        )
        return drawing

    @classmethod
    def _shapes(cls, model: Any) -> Iterable[Tuple[Any, List[Point3]]]:
        import ifcopenshell.geom

        settings: Any = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        iterator: Any = ifcopenshell.geom.iterator(settings, model)
        if not iterator.initialize():
            return

        while True:
            shape: Any = iterator.get()
            element: Any = model.by_guid(shape.guid)
            raw: List[float] = list(shape.geometry.verts)
            points: List[Point3] = [
                (float(raw[index]), float(raw[index + 1]), float(raw[index + 2]))
                for index in range(0, len(raw), 3)
            ]
            yield element, points
            if not iterator.next():
                return

    @classmethod
    def _is_plumbing(cls, element: Any) -> bool:
        for ifc_type in cls.DIRECT_PLUMBING_TYPES:
            if cls._is_a(element, ifc_type):
                return True

        if not any(
            cls._is_a(element, ifc_type)
            for ifc_type in cls.SEMANTIC_DISTRIBUTION_TYPES
        ):
            return False

        semantic_text = " ".join(
            cls._text(getattr(element, attribute, None))
            for attribute in ("Name", "Description", "ObjectType", "PredefinedType")
        ).upper()
        return any(keyword in semantic_text for keyword in cls.PLUMBING_KEYWORDS)

    @classmethod
    def _is_pipe_like(cls, element: Any) -> bool:
        if cls._is_a(element, "IfcPipeSegment"):
            return True
        if not cls._is_a(element, "IfcFlowSegment"):
            return False

        semantic_text = " ".join(
            cls._text(getattr(element, attribute, None))
            for attribute in ("Name", "Description", "ObjectType", "PredefinedType")
        ).upper()
        return any(
            keyword in semantic_text
            for keyword in (
                "PIPE",
                "PLUMB",
                "WATER",
                "ESGOTO",
                "HIDR",
                "AGUA",
                "ÁGUA",
            )
        )

    @staticmethod
    def _is_a(element: Any, ifc_type: str) -> bool:
        try:
            return bool(element.is_a(ifc_type))
        except (AttributeError, TypeError):
            try:
                return str(element.is_a()) == ifc_type
            except (AttributeError, TypeError):
                return False

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "wrappedValue"):
            value = value.wrappedValue
        return str(value)

    @classmethod
    def _centerline(cls, points: Sequence[Point3]) -> Tuple[Point3, Point3]:
        """Approximate an elongated mesh axis without adding a PCA dependency."""
        if len(points) < 2:
            point = points[0]
            return point, point

        seed = points[0]
        first = max(points, key=lambda point: cls._distance_squared(seed, point))
        second = max(points, key=lambda point: cls._distance_squared(first, point))

        direction = (
            second[0] - first[0],
            second[1] - first[1],
            second[2] - first[2],
        )
        norm = sqrt(cls._dot(direction, direction))
        if norm <= cls.PLAN_TOLERANCE:
            point = cls._centroid(points)
            return point, point

        unit = tuple(component / norm for component in direction)
        center = cls._centroid(points)
        center_projection = cls._dot(center, unit)
        projections = [cls._dot(point, unit) for point in points]
        low = min(projections) - center_projection
        high = max(projections) - center_projection

        start = tuple(center[index] + unit[index] * low for index in range(3))
        end = tuple(center[index] + unit[index] * high for index in range(3))
        return (
            (float(start[0]), float(start[1]), float(start[2])),
            (float(end[0]), float(end[1]), float(end[2])),
        )

    @classmethod
    def _add_outline(cls, modelspace: Any, points: Sequence[Point3]) -> bool:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        minimum_x, maximum_x = min(xs), max(xs)
        minimum_y, maximum_y = min(ys), max(ys)
        if (
            maximum_x - minimum_x <= cls.PLAN_TOLERANCE
            and maximum_y - minimum_y <= cls.PLAN_TOLERANCE
        ):
            cls._add_riser(modelspace, cls._centroid(points))
            return True

        modelspace.add_lwpolyline(
            [
                (minimum_x, minimum_y),
                (maximum_x, minimum_y),
                (maximum_x, maximum_y),
                (minimum_x, maximum_y),
            ],
            close=True,
            dxfattribs={"layer": cls.LAYER_NAME},
        )
        return True

    @classmethod
    def _add_riser(cls, modelspace: Any, center: Point3) -> None:
        x, y = center[0], center[1]
        half = cls.RISER_HALF_SIZE
        modelspace.add_line(
            (x - half, y - half, 0.0),
            (x + half, y + half, 0.0),
            dxfattribs={"layer": cls.LAYER_NAME},
        )
        modelspace.add_line(
            (x - half, y + half, 0.0),
            (x + half, y - half, 0.0),
            dxfattribs={"layer": cls.LAYER_NAME},
        )

    @staticmethod
    def _centroid(points: Sequence[Point3]) -> Point3:
        count = float(len(points))
        return (
            sum(point[0] for point in points) / count,
            sum(point[1] for point in points) / count,
            sum(point[2] for point in points) / count,
        )

    @staticmethod
    def _dot(left: Sequence[float], right: Sequence[float]) -> float:
        return sum(a * b for a, b in zip(left, right))

    @staticmethod
    def _distance_squared(left: Point3, right: Point3) -> float:
        return sum((left[index] - right[index]) ** 2 for index in range(3))

    @staticmethod
    def _plan_distance(left: Point3, right: Point3) -> float:
        return sqrt((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2)
