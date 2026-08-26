"""Insert a single straight pipe segment into an existing IFC at a concrete position.

The position can be supplied in two ways:

* **Absolute coordinates:** provide ``x``, ``y`` (and optional ``z``).  The
  segment is then drawn from ``(x, y, z)`` extending for ``length`` metres
  along the cardinal ``direction`` chosen (``"+x"``, ``"-y"``, ``"+z"`` etc.).
* **Reference-grid address:** provide a ``grid_ref`` string like ``"D-7"``
  or ``"D-7-β"``, matching the X-Y[-Z] tagging convention from the 3-plane
  Reference Grid.  ``GridPositioningParameter`` resolves the grid tags to a
  world-space point; a 3-D ``offset`` tuple may be added so the caller can
  nudge the pipe axis slightly off the exact grid line.

The two addressing modes are **mutually exclusive** -- choose coordinates
or ``grid_ref``, not both.  Invalid combinations raise a clear error
immediately so the failure is visible before any IFC mutation occurs.

The resulting geometric body is an ``IfcPipeSegment`` whose representation
is a solid ``IfcExtrudedAreaSolid`` using a circular profile (hollow when
``inner_diameter`` is provided), which is the same swept-solid pattern the
reference-grid lines use so everything renders consistently under the
default SURFACES_AND_SOLIDS dimensionality most viewers employ.  The pipe
is optionally attached to the hosting ``IfcBuildingStorey`` via the normal
``assign_container`` utility and an ``IfcMaterial`` with the chosen name
is linked by ``IfcRelAssociatesMaterial`` if supplied.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from infobim.ifc.adapter.flow_segment import IfcFlowSegmentBuilder
from infobim.ifc.adapter.grid_positioning import (
    GridPositioningParameter,
    resolve_positioning_parameter,
)
from infobim.ifc.adapter.representation import RepresentationContextRepository
from infobim.ifc.adapter.spatial import SpatialContainerRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.atomic_file import AtomicFileWriter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


_DIRECTION_VECTORS: Dict[str, Tuple[float, float, float]] = {
    "+x": (1.0, 0.0, 0.0),
    "-x": (-1.0, 0.0, 0.0),
    "+y": (0.0, 1.0, 0.0),
    "-y": (0.0, -1.0, 0.0),
    "+z": (0.0, 0.0, 1.0),
    "-z": (0.0, 0.0, -1.0),
}


_DEFAULT_OUTER_DIAMETER = 0.100
_DEFAULT_LENGTH = 5.0
_DEFAULT_DIRECTION = "+x"
DEFAULT_OBJECT_TYPE = "POSITIONED_PIPE_SEGMENT"


def _parse_direction_vector(direction: str) -> Tuple[float, float, float]:
    key = str(direction or "").strip().lower()
    if key not in _DIRECTION_VECTORS:
        raise ValueError(
            f"Unknown direction '{direction}'. "
            f"Valid values: {sorted(_DIRECTION_VECTORS.keys())}."
        )
    return _DIRECTION_VECTORS[key]


class PipePositioningCapability(TransactionCapability):
    """Insert a single straight pipe segment at a concrete 3D position."""

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.annotation.pipe_positioning",
        version="1.0.0",
        name="Pipe Positioning",
        description=(
            "Insert a single straight IfcPipeSegment into an existing IFC model at a "
            "chosen position.  The start point may be supplied either as raw world-"
            "space coordinates (x, y, z) or as a reference-grid address string like "
            "'D-7' or 'D-7-β', which GridPositioningParameter then resolves against "
            "the three IfcGrid planes previously written by the Reference Grid "
            "capability.  The segment extends from the resolved start point for a "
            "chosen length along a cardinal direction (+x, -y, +z etc.) and is "
            "rendered as a real IfcExtrudedAreaSolid with a circular profile so it "
            "appears correctly under the default SURFACES_AND_SOLIDS viewer setting. "
            "Optional spatial attachment to an IfcBuildingStorey (via "
            "assign_container) and material linkage (via IfcRelAssociatesMaterial) "
            "are performed when the corresponding parameters are provided."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "pipe", "positioning", "flow", "grid"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the existing .ifc file to receive the pipe.",
                },
                "x": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Absolute X coordinate in metres of the segment's start point. "
                        "Requires 'y' to be provided as well; mutually exclusive with "
                        "'grid_ref'."
                    ),
                },
                "y": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Absolute Y coordinate in metres of the segment's start point. "
                        "Required when 'x' is used."
                    ),
                },
                "z": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Absolute Z coordinate in metres of the segment's start point. "
                        "Defaults to 0.0 when omitted.  May be combined either with "
                        "x/y absolute coordinates or with a 2-component grid_ref."
                    ),
                },
                "grid_ref": {
                    "type": "string",
                    "required": False,
                    "description": (
                        "Reference-grid address such as 'D-7' or 'D-7-β' following the "
                        "X-Y[-Z] tagging convention.  Mutually exclusive with x/y/z "
                        "absolute coordinates.  The IFC must already contain the three "
                        "IfcGrid planes created by the Reference Grid capability."
                    ),
                },
                "offset": {
                    "type": "array",
                    "required": False,
                    "description": (
                        "Optional [dx, dy, dz] tuple added to the resolved start point "
                        "after either coordinate or grid_ref resolution.  Useful to "
                        "nudge a pipe slightly away from a grid axis without needing "
                        "to know exact raw coordinates."
                    ),
                },
                "direction": {
                    "type": "string",
                    "required": False,
                    "description": (
                        f"Cardinal direction the segment extends along from the start "
                        f"point.  Valid values: {sorted(_DIRECTION_VECTORS.keys())}. "
                        f"Default: '{_DEFAULT_DIRECTION}'."
                    ),
                },
                "length": {
                    "type": "number",
                    "required": False,
                    "description": (
                        f"Length in metres of the straight segment. "
                        f"Default: {_DEFAULT_LENGTH}."
                    ),
                },
                "outer_diameter": {
                    "type": "number",
                    "required": False,
                    "description": (
                        f"Pipe outer diameter in metres. "
                        f"Default: {_DEFAULT_OUTER_DIAMETER}."
                    ),
                },
                "inner_diameter": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Optional pipe inner bore diameter in metres.  When provided "
                        "(and strictly smaller than outer_diameter) a hollow circular "
                        "profile is used; otherwise the body is a solid circular rod."
                    ),
                },
                "storey_global_id": {
                    "type": "string",
                    "required": False,
                    "description": (
                        "IfcBuildingStorey GlobalId used as the spatial container "
                        "when attaching the new pipe segment.  Required only when the "
                        "model contains more than one storey and no automatic "
                        "containment is desired."
                    ),
                },
                "pipe_name": {
                    "type": "string",
                    "required": False,
                    "description": (
                        "Human-readable IfcPipeSegment.Name.  Defaults to a name "
                        "that includes the direction, length and resolved start point."
                    ),
                },
                "object_type": {
                    "type": "string",
                    "required": False,
                    "description": (
                        f"IfcPipeSegment.ObjectType.  Used by later capabilities to "
                        f"quickly enumerate every pipe created by this workflow via a "
                        f"single ObjectType filter.  Default: '{DEFAULT_OBJECT_TYPE}'."
                    ),
                },
                "material_name": {
                    "type": "string",
                    "required": False,
                    "description": (
                        "Optional IfcMaterial.Name.  When provided a lightweight "
                        "IfcRelAssociatesMaterial relation links the new segment to "
                        "a freshly-created IfcMaterial with this label."
                    ),
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "pipe_global_id": {"type": "string"},
                "pipe_name": {"type": "string"},
                "object_type": {"type": "string"},
                "positioning_mode": {"type": "string"},
                "grid_ref": {"type": ["string", "null"]},
                "start_point": {"type": "array"},
                "end_point": {"type": "array"},
                "direction": {"type": "string"},
                "length": {"type": "number"},
                "outer_diameter": {"type": "number"},
                "inner_diameter": {"type": ["number", "null"]},
                "offset": {"type": "array"},
                "storey_global_id": {"type": ["string", "null"]},
                "material_name": {"type": ["string", "null"]},
                "entities_created": {"type": "object"},
            },
        },
        log_message={
            "info": {
                "en": "A single IfcPipeSegment was inserted into the IFC file at the resolved position.",
                "pt-br": "Um único IfcPipeSegment foi inserido no arquivo IFC na posição resolvida.",
            },
            "debug_entry": {
                "en": "Resolving the start point and creating a single straight IfcPipeSegment.",
                "pt-br": "Resolvendo o ponto inicial e criando um IfcPipeSegment reto.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)

    # ── Orchestration ────────────────────────────────────────────────────────

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ifcopenshell

        ifc_path = Path(str(context.get_parameter_value("ifc_path"))).expanduser().resolve()
        if not ifc_path.is_file():
            raise ValueError(f"IFC file does not exist: {ifc_path}")

        # ── Resolve inputs ────────────────────────────────────────────────────
        x: Optional[float] = (
            float(context.get_parameter_value("x")) if context.has_parameter("x") else None
        )
        y: Optional[float] = (
            float(context.get_parameter_value("y")) if context.has_parameter("y") else None
        )
        z: Optional[float] = (
            float(context.get_parameter_value("z")) if context.has_parameter("z") else None
        )
        grid_ref: Optional[str] = (
            str(context.get_parameter_value("grid_ref"))
            if context.has_parameter("grid_ref")
            else None
        )
        raw_offset: Optional[Any] = (
            context.get_parameter_value("offset")
            if context.has_parameter("offset")
            else None
        )
        offset: Optional[Tuple[float, float, float]] = None
        if raw_offset is not None:
            try:
                iterable = list(raw_offset)
            except TypeError as exc:
                raise ValueError("'offset' must be a 3-element array [dx, dy, dz].") from exc
            if len(iterable) != 3:
                raise ValueError("'offset' must be a 3-element array [dx, dy, dz].")
            offset = (float(iterable[0]), float(iterable[1]), float(iterable[2]))

        direction_raw = (
            str(context.get_parameter_value("direction"))
            if context.has_parameter("direction")
            else _DEFAULT_DIRECTION
        )
        length_raw = (
            float(context.get_parameter_value("length"))
            if context.has_parameter("length")
            else _DEFAULT_LENGTH
        )
        outer_diameter = (
            float(context.get_parameter_value("outer_diameter"))
            if context.has_parameter("outer_diameter")
            else _DEFAULT_OUTER_DIAMETER
        )
        inner_diameter: Optional[float] = (
            float(context.get_parameter_value("inner_diameter"))
            if context.has_parameter("inner_diameter")
            else None
        )
        storey_global_id: Optional[str] = (
            str(context.get_parameter_value("storey_global_id"))
            if context.has_parameter("storey_global_id")
            else None
        )
        pipe_name_override: Optional[str] = (
            str(context.get_parameter_value("pipe_name"))
            if context.has_parameter("pipe_name")
            else None
        )
        object_type_raw: Optional[str] = (
            str(context.get_parameter_value("object_type"))
            if context.has_parameter("object_type")
            else DEFAULT_OBJECT_TYPE
        )
        material_name: Optional[str] = (
            str(context.get_parameter_value("material_name"))
            if context.has_parameter("material_name")
            else None
        )

        # ── Validate numeric values ───────────────────────────────────────────
        direction_vec = _parse_direction_vector(direction_raw)
        direction_key = direction_raw.strip().lower()
        if float(length_raw) <= 0:
            raise ValueError("'length' must be greater than zero.")
        if float(outer_diameter) <= 0:
            raise ValueError("'outer_diameter' must be greater than zero.")
        if inner_diameter is not None and float(inner_diameter) >= float(outer_diameter):
            raise ValueError("'inner_diameter' must be strictly smaller than 'outer_diameter'.")

        # ── Open model & resolve positioning ──────────────────────────────────
        model = ifcopenshell.open(str(ifc_path))

        positioned: GridPositioningParameter = resolve_positioning_parameter(
            model,
            x=x, y=y, z=z,
            grid_ref=grid_ref,
            offset=offset,
        )

        start = positioned.point
        end: Tuple[float, float, float] = (
            start[0] + direction_vec[0] * length_raw,
            start[1] + direction_vec[1] * length_raw,
            start[2] + direction_vec[2] * length_raw,
        )

        # ── IFC context / spatial host ────────────────────────────────────────
        ctx_repo = RepresentationContextRepository(model)
        body_context = ctx_repo.get_body()

        spatial_repo = SpatialContainerRepository(model)
        storey: Optional[Any] = None
        if storey_global_id is not None or len(spatial_repo.list_storeys()) == 1:
            storey = spatial_repo.get_storey(storey_global_id)

        # ── Build pipe ────────────────────────────────────────────────────────
        entities_created: Dict[str, int] = {}
        builder = IfcFlowSegmentBuilder(model, entities_created)
        resolved_pipe_name = pipe_name_override or self._default_pipe_name(
            direction_key, length_raw, start
        )
        segment = builder.create_pipe_segment(
            body_context=body_context,
            start=start,
            end=end,
            outer_diameter=outer_diameter,
            inner_diameter=inner_diameter,
            storey=storey,
            name=resolved_pipe_name,
            description=(
                f"Positioned pipe segment from {start} to {end}. "
                f"Positioning mode: {positioned.source.kind}."
            ),
            object_type=object_type_raw,
            material_name=material_name,
        )

        # ── Atomic write ──────────────────────────────────────────────────────
        AtomicFileWriter.write(ifc_path, lambda tmp: model.write(str(tmp)))

        return {
            "ifc_path": str(ifc_path),
            "pipe_global_id": str(getattr(segment, "GlobalId", "") or ""),
            "pipe_name": resolved_pipe_name,
            "object_type": str(object_type_raw or ""),
            "positioning_mode": positioned.source.kind,
            "grid_ref": positioned.source.grid_ref,
            "start_point": list(start),
            "end_point": list(end),
            "direction": direction_key,
            "length": float(length_raw),
            "outer_diameter": float(outer_diameter),
            "inner_diameter": None if inner_diameter is None else float(inner_diameter),
            "offset": list(positioned.source.offset),
            "storey_global_id": None if storey is None else str(getattr(storey, "GlobalId", "") or ""),
            "material_name": None if material_name is None else str(material_name),
            "entities_created": entities_created,
        }

    # ── Presentation helpers ─────────────────────────────────────────────────

    @staticmethod
    def _default_pipe_name(
        direction: str, length: float, start: Tuple[float, float, float],
    ) -> str:
        sx, sy, sz = (round(value, 3) for value in start)
        return (
            f"Pipe {direction} L={round(length, 3)}m "
            f"@({sx}, {sy}, {sz})"
        )
