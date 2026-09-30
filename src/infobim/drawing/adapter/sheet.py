from typing import Any, ClassVar, List, Optional, Tuple

from ezdxf import bbox
from ezdxf.document import Drawing
from ezdxf.entities import DXFGraphic

from infobim.drawing.domain.model.view import DrawingBoundary
from infobim.drawing.domain.model.sheet import SheetEntity


class DxfSheetIndex:
    """
    Read the model space of a sheet into the entities view discovery uses.

    Each entity is measured once, with its extents in drawing coordinates.
    Texts keep their plain content and height, block references their
    block name and the attributes they carry, closed axis-aligned
    four-sided polylines are flagged as rectangles and circles keep their
    radius. An entity without measurable extents occupies no region of the
    sheet and is left out.
    """

    TEXT_TYPES: ClassVar[Tuple[str, ...]] = ("TEXT", "MTEXT", "ATTRIB")
    POLYLINE_TYPES: ClassVar[Tuple[str, ...]] = ("LWPOLYLINE", "POLYLINE")
    RECTANGLE_TOLERANCE: ClassVar[float] = 1e-6

    @classmethod
    def of(cls, document: Drawing) -> List[SheetEntity]:
        cache: bbox.Cache = bbox.Cache()
        entities: List[SheetEntity] = []
        entity: DXFGraphic
        for entity in document.modelspace():
            measured: Optional[SheetEntity] = cls._measured(entity, cache, None)
            if measured is None:
                continue
            entities.append(measured)
            if entity.dxftype() == "INSERT":
                attribute: DXFGraphic
                for attribute in entity.attribs:
                    read: Optional[SheetEntity] = cls._measured(
                        attribute, cache, measured.handle
                    )
                    if read is not None:
                        entities.append(read)
        return entities

    @classmethod
    def _measured(
        cls,
        entity: DXFGraphic,
        cache: bbox.Cache,
        owner_handle: Optional[str],
    ) -> Optional[SheetEntity]:
        extents: bbox.BoundingBox = bbox.extents([entity], cache=cache)
        if not extents.has_data:
            return None

        dxftype: str = entity.dxftype()
        text: Optional[str] = cls._text_of(entity) if dxftype in cls.TEXT_TYPES else None
        return SheetEntity(
            handle=entity.dxf.handle,
            dxftype=dxftype,
            boundary=DrawingBoundary(
                float(extents.extmin.x),
                float(extents.extmin.y),
                float(extents.extmax.x),
                float(extents.extmax.y),
            ),
            text=text,
            text_height=cls._text_height_of(entity) if text is not None else None,
            block_name=entity.dxf.name if dxftype == "INSERT" else None,
            rectangle=dxftype in cls.POLYLINE_TYPES and cls._is_rectangle(entity),
            radius=float(entity.dxf.radius) if dxftype == "CIRCLE" else None,
            owner_handle=owner_handle,
        )

    @staticmethod
    def _text_of(entity: DXFGraphic) -> str:
        if entity.dxftype() == "MTEXT":
            return str(entity.plain_text()).strip()
        return str(entity.dxf.text).strip()

    @staticmethod
    def _text_height_of(entity: DXFGraphic) -> float:
        if entity.dxftype() == "MTEXT":
            return float(entity.dxf.char_height)
        return float(entity.dxf.height)

    @classmethod
    def _is_rectangle(cls, entity: DXFGraphic) -> bool:
        points: List[Tuple[float, float]] = cls._vertices_of(entity)
        if len(points) > 4 and cls._same(points[0], points[-1]):
            points = points[:-1]
        if len(points) != 4 or not (entity.is_closed or cls._same(points[0], points[-1])):
            return False

        index: int
        for index in range(4):
            start: Tuple[float, float] = points[index]
            end: Tuple[float, float] = points[(index + 1) % 4]
            horizontal: bool = abs(start[1] - end[1]) <= cls.RECTANGLE_TOLERANCE
            vertical: bool = abs(start[0] - end[0]) <= cls.RECTANGLE_TOLERANCE
            if horizontal == vertical:
                return False
        return True

    @staticmethod
    def _vertices_of(entity: DXFGraphic) -> List[Tuple[float, float]]:
        if entity.dxftype() == "LWPOLYLINE":
            if entity.has_arc:
                return []
            return [(float(x), float(y)) for x, y in entity.get_points(format="xy")]
        if not entity.is_2d_polyline:
            return []
        vertices: List[Any] = list(entity.vertices)
        if any(vertex.dxf.bulge != 0 for vertex in vertices):
            return []
        return [
            (float(vertex.dxf.location.x), float(vertex.dxf.location.y))
            for vertex in vertices
        ]

    @classmethod
    def _same(cls, first: Tuple[float, float], second: Tuple[float, float]) -> bool:
        return (
            abs(first[0] - second[0]) <= cls.RECTANGLE_TOLERANCE
            and abs(first[1] - second[1]) <= cls.RECTANGLE_TOLERANCE
        )
