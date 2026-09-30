from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Sequence, Tuple

import ezdxf
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.ifcopenshell_wrapper as ifc_wrapper

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


Point2D = Tuple[float, float]
Segment2D = Tuple[Point2D, Point2D]
NativeRepresentationRef = Tuple[int, int, str]


class _SectionCapability(TransactionCapability):
    """Common metadata helpers for the IFC section state capabilities."""

    STATE_NAME: ClassVar[str]

    def label(self, lang: str = "en") -> str:
        return self.METADATA.name

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description

    @staticmethod
    def _metadata(state_name: str, description: str) -> CapabilityMetadata:
        return CapabilityMetadata(
            id=(
                "org.infobim.drawing.plugin.capability.transformation."
                f"section.target.{state_name}"
            ),
            version="1.0.0",
            name=f"IFC section: {state_name.replace('_', ' ')}",
            description=description,
            author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
            tags=["infobim", "drawing", "ifc", "dxf", "2d", "fsm"],
            supported_languages=["en", "pt-br"],
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
        )


class IfcSectionIfcLoadedCapability(_SectionCapability):
    METADATA = _SectionCapability._metadata(
        "ifc_loaded",
        "Load the IFC source model for the 2D section state machine.",
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        source = Path(
            str(context.get_parameter_value("ifc_path"))
        ).expanduser().resolve()
        try:
            model = ifcopenshell.open(str(source))
        except Exception as error:
            raise ValueError(f"Could not open IFC file: {source}: {error}") from error

        context.set_parameter_value("section_ifc_model", model)
        return {"section_ifc_loaded": True}


class IfcSectionRepresentationsInspectedCapability(_SectionCapability):
    METADATA = _SectionCapability._metadata(
        "representations_inspected",
        "Inspect products for native PLAN_VIEW / FootPrint / Annotation geometry.",
    )

    NATIVE_IDENTIFIERS: ClassVar[set[str]] = {
        "footprint",
        "annotation",
        "axis",
        "plan",
    }

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        model = context.get_parameter_value("section_ifc_model")
        refs: List[NativeRepresentationRef] = []

        for product in model.by_type("IfcProduct"):
            product_representation = getattr(product, "Representation", None)
            if product_representation is None:
                continue

            for representation in (
                getattr(product_representation, "Representations", None) or []
            ):
                identifier = str(
                    getattr(representation, "RepresentationIdentifier", "") or ""
                )
                representation_context = getattr(
                    representation, "ContextOfItems", None
                )
                target_view = str(
                    getattr(representation_context, "TargetView", "") or ""
                ).upper()

                is_plan_view = target_view == "PLAN_VIEW"
                is_native_identifier = (
                    identifier.strip().casefold() in self.NATIVE_IDENTIFIERS
                )
                if is_plan_view and is_native_identifier:
                    refs.append(
                        (product.id(), representation.id(), identifier or "Plan")
                    )

        context.set_parameter_value("section_native_representations", refs)
        context.set_parameter_value(
            "section_native_plan_available", bool(refs)
        )
        return {
            "section_native_plan_available": bool(refs),
            "section_native_representation_count": len(refs),
        }


class IfcSectionNativePlanExtractedCapability(_SectionCapability):
    METADATA = _SectionCapability._metadata(
        "native_plan_extracted",
        "Extract native IFC PLAN_VIEW curves in world coordinates.",
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        model = context.get_parameter_value("section_ifc_model")
        refs: Sequence[NativeRepresentationRef] = context.get_parameter_value(
            "section_native_representations"
        )

        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        settings.set(
            "dimensionality",
            ifc_wrapper.CURVES_SURFACES_AND_SOLIDS,
        )

        segments: List[Segment2D] = []
        native_product_ids: set[int] = set()
        successful_native_product_ids: set[int] = set()

        for product_id, representation_id, _identifier in refs:
            native_product_ids.add(product_id)
            product = model.by_id(product_id)
            representation = model.by_id(representation_id)
            try:
                shape = ifcopenshell.geom.create_shape(
                    settings,
                    product,
                    representation,
                )
            except RuntimeError:
                continue

            geometry = shape.geometry
            representation_segments = _segments_from_edges(
                getattr(geometry, "verts", ()),
                getattr(geometry, "edges", ()),
            )
            if representation_segments:
                successful_native_product_ids.add(product_id)
                segments.extend(representation_segments)

        z = float(context.get_parameter_value("section_z"))
        fallback_segments, fallback_products = _body_section_segments(
            model,
            z,
            exclude_product_ids=successful_native_product_ids,
        )
        segments.extend(fallback_segments)
        segments = _deduplicate_segments(segments)
        if not segments:
            raise ValueError(
                "The IFC produced no native plan geometry and no Body "
                f"section geometry at Z={z} m."
            )

        strategy = (
            "native_plan"
            if fallback_products == 0
            else "native_plan+body_fallback"
        )
        context.set_parameter_value("section_segments", segments)
        context.set_parameter_value("section_strategy", strategy)
        context.set_parameter_value("section_segment_count", len(segments))
        return {
            "section_strategy": strategy,
            "section_segment_count": len(segments),
            "section_native_products": len(successful_native_product_ids),
            "section_body_fallback_products": fallback_products,
        }


class IfcSectionBodySectionGeneratedCapability(_SectionCapability):
    METADATA = _SectionCapability._metadata(
        "body_section_generated",
        "Intersect tessellated IFC Body geometry with a horizontal Z plane.",
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        model = context.get_parameter_value("section_ifc_model")
        z = float(context.get_parameter_value("section_z"))

        segments, products_processed = _body_section_segments(model, z)
        segments = _deduplicate_segments(segments)
        if not segments:
            raise ValueError(
                f"The IFC Body produced no section geometry at Z={z} m."
            )

        context.set_parameter_value("section_segments", segments)
        context.set_parameter_value("section_strategy", "body_section")
        context.set_parameter_value("section_segment_count", len(segments))
        return {
            "section_strategy": "body_section",
            "section_segment_count": len(segments),
            "section_products_processed": products_processed,
        }


class IfcSectionDxfWrittenCapability(_SectionCapability):
    METADATA = _SectionCapability._metadata(
        "dxf_written",
        "Write the state-machine 2D segments to a DXF file.",
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        source = Path(
            str(context.get_parameter_value("ifc_path"))
        ).expanduser().resolve()
        z = float(context.get_parameter_value("section_z"))
        segments: Sequence[Segment2D] = context.get_parameter_value(
            "section_segments"
        )

        z_token = format(z, ".15g").replace("-", "m").replace(".", "_")
        output = source.with_name(f"{source.stem}.section-z-{z_token}.dxf")

        document = ezdxf.new("R2018", setup=True)
        modelspace = document.modelspace()
        for start, end in segments:
            modelspace.add_line(start, end)

        document.header["$INSUNITS"] = 6  # metres
        document.saveas(output)

        context.set_parameter_value("section_dxf_path", str(output))
        return {
            "section_dxf_path": str(output),
            "section_segment_count": len(segments),
        }


def _body_section_segments(
    model: Any,
    z: float,
    exclude_product_ids: Optional[set[int]] = None,
) -> Tuple[List[Segment2D], int]:
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)

    excluded = exclude_product_ids or set()
    segments: List[Segment2D] = []
    products_processed = 0

    for product in model.by_type("IfcProduct"):
        if product.id() in excluded:
            continue
        if getattr(product, "Representation", None) is None:
            continue
        try:
            shape = ifcopenshell.geom.create_shape(settings, product)
        except RuntimeError:
            continue

        geometry = shape.geometry
        verts = _vertices3(getattr(geometry, "verts", ()))
        faces = list(getattr(geometry, "faces", ()))
        if not verts or not faces:
            continue

        product_has_section = False
        for index in range(0, len(faces) - 2, 3):
            try:
                triangle = (
                    verts[int(faces[index])],
                    verts[int(faces[index + 1])],
                    verts[int(faces[index + 2])],
                )
            except (IndexError, ValueError):
                continue
            segment = _triangle_plane_segment(triangle, z)
            if segment is not None:
                segments.append(segment)
                product_has_section = True

        if product_has_section:
            products_processed += 1

    return segments, products_processed


def _segments_from_edges(
    raw_vertices: Iterable[float],
    raw_edges: Iterable[int],
) -> List[Segment2D]:
    verts = _vertices3(raw_vertices)
    edges = list(raw_edges)
    segments: List[Segment2D] = []
    for index in range(0, len(edges) - 1, 2):
        try:
            start = verts[int(edges[index])]
            end = verts[int(edges[index + 1])]
        except (IndexError, ValueError):
            continue
        segment = ((start[0], start[1]), (end[0], end[1]))
        if not _same_point(*segment):
            segments.append(segment)
    return segments


def _vertices3(
    raw_vertices: Iterable[float],
) -> List[Tuple[float, float, float]]:
    values = list(raw_vertices)
    return [
        (float(values[index]), float(values[index + 1]), float(values[index + 2]))
        for index in range(0, len(values) - 2, 3)
    ]


def _triangle_plane_segment(
    triangle: Tuple[
        Tuple[float, float, float],
        Tuple[float, float, float],
        Tuple[float, float, float],
    ],
    z: float,
    tolerance: float = 1e-9,
) -> Optional[Segment2D]:
    points: List[Point2D] = []

    for start, end in (
        (triangle[0], triangle[1]),
        (triangle[1], triangle[2]),
        (triangle[2], triangle[0]),
    ):
        dz_start = start[2] - z
        dz_end = end[2] - z

        if abs(dz_start) <= tolerance and abs(dz_end) <= tolerance:
            continue

        if abs(dz_start) <= tolerance:
            points.append((start[0], start[1]))
            continue
        if abs(dz_end) <= tolerance:
            points.append((end[0], end[1]))
            continue

        if (dz_start < 0.0 < dz_end) or (dz_end < 0.0 < dz_start):
            t = (z - start[2]) / (end[2] - start[2])
            points.append(
                (
                    start[0] + t * (end[0] - start[0]),
                    start[1] + t * (end[1] - start[1]),
                )
            )

    unique = _unique_points(points, tolerance)
    if len(unique) < 2:
        return None

    if len(unique) > 2:
        pairs = [
            (unique[i], unique[j])
            for i in range(len(unique))
            for j in range(i + 1, len(unique))
        ]
        start, end = max(
            pairs,
            key=lambda pair: (
                (pair[1][0] - pair[0][0]) ** 2
                + (pair[1][1] - pair[0][1]) ** 2
            ),
        )
    else:
        start, end = unique[0], unique[1]

    if _same_point(start, end, tolerance):
        return None
    return start, end


def _unique_points(
    points: Iterable[Point2D],
    tolerance: float,
) -> List[Point2D]:
    unique: List[Point2D] = []
    for point in points:
        if not any(_same_point(point, other, tolerance) for other in unique):
            unique.append(point)
    return unique


def _same_point(
    first: Point2D,
    second: Point2D,
    tolerance: float = 1e-9,
) -> bool:
    return (
        abs(first[0] - second[0]) <= tolerance
        and abs(first[1] - second[1]) <= tolerance
    )


def _deduplicate_segments(
    segments: Iterable[Segment2D],
    precision: int = 9,
) -> List[Segment2D]:
    seen: set[
        Tuple[Tuple[float, float], Tuple[float, float]]
    ] = set()
    result: List[Segment2D] = []

    for start, end in segments:
        a = (round(start[0], precision), round(start[1], precision))
        b = (round(end[0], precision), round(end[1], precision))
        key = (a, b) if a <= b else (b, a)
        if key in seen or a == b:
            continue
        seen.add(key)
        result.append((start, end))

    return result
