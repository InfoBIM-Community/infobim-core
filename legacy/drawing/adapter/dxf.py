"""Convert supported modelspace CAD paths into independent IFCX curves."""

from math import isfinite
from uuid import NAMESPACE_URL, uuid5
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
)
from pathlib import Path
from collections import Counter
from dataclasses import dataclass

import ezdxf
from ezdxf.bbox import extents
from ezdxf.math import BoundingBox, BoundingBox2d, Vec3
from ezdxf.path import Path as CadPath, make_path
from ezdxf.units import M, conversion_factor
from ezdxf.layouts import Paperspace
from ezdxf.document import Drawing
from ezdxf.entities import DXFEntity, Insert, Polyline

from infobim.drawing.model import DrawingPlacement, IfcxDocument
from infobim.drawing.adapter.viewport_projection import ViewportProjection


@dataclass(frozen=True)
class DxfConversion:
    document: Dict[str, Any]
    root: str
    paths: int
    unsupported: Dict[str, int]


class DxfConverter:
    SUPPORTED: ClassVar[Set[str]] = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE"}
    TOLERANCE_METRES: ClassVar[float] = 0.001
    MAX_BLOCK_DEPTH: ClassVar[int] = 8

    @classmethod
    def convert(
        cls,
        source: Path,
        identifier: str,
        placement: Optional[DrawingPlacement] = None,
    ) -> DxfConversion:
        drawing: Drawing = ezdxf.readfile(source)
        return cls.from_drawing(drawing, source.name, identifier, placement)

    @classmethod
    def from_drawing(
        cls,
        drawing: Drawing,
        name: str,
        identifier: str,
        placement: Optional[DrawingPlacement] = None,
    ) -> DxfConversion:
        resolved: DrawingPlacement = DrawingPlacement() if placement is None else placement
        scale: float = cls._unit_scale(drawing, resolved)
        root: str = f"drawing_{uuid5(NAMESPACE_URL, identifier).hex}"
        nodes: List[Dict[str, Any]] = []
        children: Dict[str, str] = {}
        unsupported: Counter[str] = Counter()
        for entity, handle, kind in cls._iter_supported(drawing.modelspace(), unsupported):
            for child_name, node in cls._curve_nodes(root, entity, handle, kind, scale):
                children[child_name] = node["path"]
                nodes.append(node)
        if not nodes:
            raise ValueError(f"CAD drawing contains no supported modelspace paths: {name}; found {dict(unsupported)}")
        nodes.insert(0, {
            "path": root,
            "children": children,
            "attributes": {
                "infobim::name": name,
                "usd::xformop": {"transform": resolved.with_unit_scale(scale)},
            },
        })
        return DxfConversion(
            document=IfcxDocument.create(identifier, nodes),
            root=root,
            paths=len(children),
            unsupported=dict(unsupported),
        )

    @classmethod
    def from_layout(
        cls,
        drawing: Drawing,
        layout_name: str,
        name: str,
        identifier: str,
    ) -> DxfConversion:
        """
        Convert one paper-space layout into a flat 2D snapshot: the
        layout's own entities (title block, border, annotations) plus,
        for each of its viewports, the Model geometry that viewport
        frames, projected from WCS into the same paper-space coordinates
        a plot would show it in. The result is what printing that
        prancha would produce, in one flat coordinate system -- not
        Model kept in its own 3D frame alongside it.

        VIEWPORT entities themselves are never drawn: by AutoCAD
        convention they live on a non-plotting layer (DEFPOINTS), since
        here they are the mapping used to place Model's geometry, not
        geometry of their own. Viewport id 1 is excluded from that
        mapping for the same reason DxfLayoutSplitter excludes it: it is
        paper space's own overall view, not a floating detail window.

        There is no DrawingPlacement here, unlike from_drawing: a
        snapshot is the layout's own paper, not a drawing placed in a
        shared building coordinate system.
        """
        layout: Paperspace = drawing.layout(layout_name)
        scale: float = cls._unit_scale(drawing, DrawingPlacement())
        root: str = f"drawing_{uuid5(NAMESPACE_URL, identifier).hex}"
        nodes: List[Dict[str, Any]] = []
        children: Dict[str, str] = {}
        unsupported: Counter[str] = Counter()

        paper_entities: Iterator[DXFEntity] = (
            entity for entity in layout if entity.dxftype() != "VIEWPORT"
        )
        for entity, handle, kind in cls._iter_supported(paper_entities, unsupported):
            for child_name, node in cls._curve_nodes(root, entity, handle, kind, scale):
                children[child_name] = node["path"]
                nodes.append(node)

        projections: List[ViewportProjection] = [
            ViewportProjection(entity)
            for entity in layout
            if entity.dxftype() == "VIEWPORT"
            and entity.dxf.id != ViewportProjection.OVERALL_VIEWPORT_ID
        ]
        model_entities: List[Tuple[DXFEntity, str, str, BoundingBox2d]] = []
        for entity, handle, kind in cls._iter_supported(drawing.modelspace(), unsupported):
            box: BoundingBox = extents([entity])
            if not box.has_data:
                continue
            model_entities.append(
                (entity, handle, kind, BoundingBox2d([box.extmin, box.extmax]))
            )

        index: int
        projection: ViewportProjection
        for index, projection in enumerate(projections):
            window: BoundingBox2d = projection.window()
            for entity, handle, kind, entity_window in model_entities:
                if not window.has_overlap(entity_window):
                    continue
                for child_name, node in cls._curve_nodes(
                    root,
                    entity,
                    f"vp{index}_{handle}",
                    kind,
                    scale,
                    window=window,
                    transform=projection.to_paper,
                ):
                    children[child_name] = node["path"]
                    nodes.append(node)

        if not nodes:
            raise ValueError(
                f"CAD layout snapshot contains no supported paths: {name}; "
                f"found {dict(unsupported)}"
            )
        nodes.insert(0, {
            "path": root,
            "children": children,
            "attributes": {
                "infobim::name": name,
                "usd::xformop": {"transform": DrawingPlacement().with_unit_scale(scale)},
            },
        })
        return DxfConversion(
            document=IfcxDocument.create(identifier, nodes),
            root=root,
            paths=len(children),
            unsupported=dict(unsupported),
        )

    @classmethod
    def _curve_nodes(
        cls,
        root: str,
        entity: DXFEntity,
        handle: str,
        kind: str,
        scale: float,
        window: Optional[BoundingBox2d] = None,
        transform: Optional[Callable[[Vec3], Vec3]] = None,
    ) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """
        Build the IFCX curve node(s) for one entity, in root's namespace.

        Flattening always happens in the entity's own native space, at a
        tolerance derived from scale. When window is given, the flattened
        polyline is clipped to it first: an entity chosen because its
        bounding box overlaps a viewport's window (the cheap pre-filter
        callers use before reaching here) can still run on well past the
        window's actual edges, and only the part of it the viewport truly
        frames belongs in the snapshot. Clipping can split one entity
        into several disconnected runs, or remove it entirely, so this
        yields zero, one, or several nodes rather than exactly one.
        transform, when given, is applied to each surviving vertex
        afterward -- projecting it into paper space -- after clipping,
        so the clip itself always happens in the same WCS window is
        expressed in.
        """
        curve: CadPath = make_path(entity)
        if curve.has_sub_paths:
            raise ValueError(f"DXF {kind} {handle} unexpectedly contains multiple paths.")
        vertices: List[Vec3] = list(curve.flattening(cls.TOLERANCE_METRES / scale, segments=8))

        chains: List[List[Vec3]] = (
            [vertices] if window is None else cls._clip_polyline(vertices, window)
        )

        chain: List[Vec3]
        index: int
        for index, chain in enumerate(chains):
            points: List[Vec3] = (
                chain if transform is None else [transform(vertex) for vertex in chain]
            )
            if not all(isfinite(value) for point in points for value in point):
                raise ValueError(f"DXF {kind} {handle} has invalid or empty geometry.")
            suffix: str = handle if len(chains) == 1 else f"{handle}_{index}"
            child_name: str = f"{kind}_{suffix}"
            path: str = f"{root}_{child_name}"
            yield child_name, {
                "path": path,
                "attributes": {
                    "infobim::name": f"{kind} {suffix}",
                    "usd::usdgeom::basiscurves": {
                        "points": [[point.x, point.y, point.z] for point in points],
                        "curveVertexCounts": [len(points)],
                        "type": "linear",
                        "wrap": "nonperiodic",
                    },
                },
            }

    @classmethod
    def _clip_polyline(
        cls, vertices: List[Vec3], window: BoundingBox2d
    ) -> List[List[Vec3]]:
        """
        Clip an open polyline to window's X/Y extents, in the polyline's
        own coordinate space.

        Each maximal run of the polyline that stays inside window becomes
        one entry; a run that exits and re-enters window produces
        separate entries rather than one entry with a gap jumped across.
        """
        chains: List[List[Vec3]] = []
        current: List[Vec3] = []
        previous_end_survived: bool = False
        start: Vec3
        end: Vec3
        for start, end in zip(vertices, vertices[1:]):
            clipped: Optional[Tuple[Vec3, Vec3, float, float]] = cls._clip_segment(
                start, end, window
            )
            if clipped is None:
                if len(current) >= 2:
                    chains.append(current)
                current = []
                previous_end_survived = False
                continue
            clipped_start, clipped_end, entry, exit_ = clipped
            if not (previous_end_survived and entry == 0.0):
                if len(current) >= 2:
                    chains.append(current)
                current = [clipped_start]
            current.append(clipped_end)
            previous_end_survived = exit_ == 1.0
        if len(current) >= 2:
            chains.append(current)
        return chains

    @staticmethod
    def _clip_segment(
        start: Vec3, end: Vec3, window: BoundingBox2d
    ) -> Optional[Tuple[Vec3, Vec3, float, float]]:
        """
        Clip one segment to window's X/Y extents via Liang-Barsky.

        Returns the clipped endpoints plus the entry/exit fraction along
        the original segment (0.0 / 1.0 when that end was not clipped
        away), so a caller can tell an untouched shared vertex between
        two consecutive segments from one Liang-Barsky itself computed --
        the two are not guaranteed bit-identical -- without comparing
        floating-point points for closeness.

        Z is not clipped against, only carried along linearly with the
        surviving X/Y range, since window is a flat 2D crop.
        """
        delta_x: float = end.x - start.x
        delta_y: float = end.y - start.y
        entry: float = 0.0
        exit_: float = 1.0
        boundary: float
        distance: float
        for boundary, distance in (
            (-delta_x, start.x - window.extmin.x),
            (delta_x, window.extmax.x - start.x),
            (-delta_y, start.y - window.extmin.y),
            (delta_y, window.extmax.y - start.y),
        ):
            if boundary == 0:
                if distance < 0:
                    return None
                continue
            position: float = distance / boundary
            if boundary < 0:
                if position > exit_:
                    return None
                entry = max(entry, position)
            else:
                if position < entry:
                    return None
                exit_ = min(exit_, position)
        if entry > exit_:
            return None
        return start + (end - start) * entry, start + (end - start) * exit_, entry, exit_

    @classmethod
    def _iter_supported(
        cls,
        entities: Iterable[DXFEntity],
        unsupported: Counter[str],
        prefix: str = "",
        depth: int = 0,
    ) -> Iterator[Tuple[DXFEntity, str, str]]:
        """
        Yield every supported entity, expanding INSERT block references.

        A block reference contributes no geometry of its own: its supported
        entities are the block definition's, transformed into the space the
        INSERT lives in. ezdxf's virtual_entities() already applies that
        transform, so recursing into it is enough; nesting depth is capped
        against a circular block reference.

        Virtual entities carry no handle of their own (they are synthesized,
        not stored in the file), so each is given a synthetic one derived
        from its enclosing INSERT's real handle and its position within it,
        chained through nested block references for uniqueness.
        """
        if depth > cls.MAX_BLOCK_DEPTH:
            raise ValueError("DXF block references are nested too deeply.")
        index: int
        entity: DXFEntity
        for index, entity in enumerate(entities):
            kind: str = entity.dxftype()
            if kind == "INSERT":
                insert: Insert = entity
                insert_handle: Any = insert.dxf.handle
                insert_id: str = (
                    insert_handle
                    if isinstance(insert_handle, str) and insert_handle
                    else f"{prefix}_{index}" if prefix else str(index)
                )
                yield from cls._iter_supported(
                    insert.virtual_entities(), unsupported, insert_id, depth + 1,
                )
                continue
            if kind not in cls.SUPPORTED:
                unsupported[kind] += 1
                continue
            if isinstance(entity, Polyline) and (entity.is_polygon_mesh or entity.is_poly_face_mesh):
                unsupported["POLYLINE_MESH"] += 1
                continue
            handle: Any = entity.dxf.handle
            if not isinstance(handle, str) or not handle:
                handle = f"{prefix}_{index}" if prefix else str(index)
            yield entity, handle, kind

    @staticmethod
    def _unit_scale(drawing: Drawing, placement: DrawingPlacement) -> float:
        if placement.meters_per_unit is not None:
            return placement.meters_per_unit
        units: int = drawing.units
        if units == 0:
            raise ValueError(
                "DXF $INSUNITS is unitless. Declare meters_per_unit for this drawing "
                "in the Project's .__infobim__/3d.json."
            )
        scale: float = conversion_factor(units, M)
        if not isfinite(scale) or scale <= 0:
            raise ValueError(f"Unsupported DXF drawing units: {units}")
        return scale
