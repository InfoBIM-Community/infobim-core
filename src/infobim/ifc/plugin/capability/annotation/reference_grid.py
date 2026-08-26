"""Annotate an existing IFC with a 3D spatial reference grid.

Semantic convention:
- X axis: Latin alphabetic references: A, B, C, ... Z, AA, BB, CC, ...
- Y axis: numeric references: 1, 2, 3, ...
- Z axis: Greek references: α, β, γ, ... ω, αα, ββ, γγ, ...

The XY, XZ and YZ planes are each a real IfcGrid: IfcGrid's ObjectPlacement
is a full IfcAxis2Placement3D, not restricted to the horizontal plane, so
the XZ/YZ grids are simply IfcGrid instances rotated to lie in those
planes, with genuine UAxes/VAxes rather than an IfcAnnotation workaround.
IfcAnnotation is still used, but only for the per-axis IfcTextLiteral tags.

The grid is a positioning aid. It does not georeference the model or
change the coordinate system of existing BIM elements.

The concrete geometric primitives, axis-tagging scheme and single-plane
grid builder are delegated to dedicated adapters under
``infobim.ifc.adapter.*`` — this module contains only the capability's
own constants, metadata and the top-level ``execute`` orchestration.
"""

from pathlib import Path
from typing import Any, Dict, List

from infobim.ifc.adapter.geometry import ModelExtentsService
from infobim.ifc.adapter.grid_reference import (
    GRID_LABEL_OBJECT_TYPE,
    GRID_NAME_XY,
    GRID_NAME_XZ,
    GRID_NAME_YZ,
    GRID_NAMES,
    axis_positions,
    build_reference_grid_plane,
    greek_tags,
    latin_tags,
    new_entity_counter,
    ordinal_tags,
    standard_3plane_frames,
)
from infobim.ifc.adapter.representation import RepresentationContextRepository
from infobim.ifc.adapter.spatial import SpatialContainerRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.atomic_file import AtomicFileWriter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.scale import ScaleMath
from ontobdc.shared.domain.model.capability import CapabilityMetadata


_LINE_THICKNESS_DEFAULT = 0.03


class ReferenceGridCapability(TransactionCapability):
    """Insert a three-dimensional spatial reference grid into an IFC model."""

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.annotation.reference_grid",
        version="1.1.0",
        name="Reference Grid",
        description=(
            "Insert a regular 3D spatial reference grid into an existing IFC model, as "
            "three real IfcGrid instances -- one per principal plane (XY, XZ, YZ), each "
            "with genuine UAxes/VAxes, IfcGrid's ObjectPlacement being rotated to fit the "
            "XZ/YZ planes rather than modelled as a generic annotation workaround. X "
            "references are alphabetic, Y references are numeric, and Z references use "
            "Greek letters, so any point can be addressed without reading raw coordinates "
            "(e.g. D-7-β). Does not alter existing BIM geometry or placements."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "grid", "reference", "positioning"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the existing .ifc file to annotate.",
                },
                "spacing": {
                    "type": "number",
                    "required": False,
                    "description": "Positive grid spacing in metres. Computed automatically when omitted.",
                },
                "margin": {
                    "type": "number",
                    "required": False,
                    "description": "Non-negative margin in metres beyond model extents. Defaults to one grid module.",
                },
                "storey_global_id": {
                    "type": "string",
                    "required": False,
                    "description": (
                        "IfcBuildingStorey GlobalId used as the spatial container for the grids. "
                        "Required when the model has more than one storey."
                    ),
                },
                "line_thickness": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Cross-section (metres) of the extruded rod used to draw every grid line. "
                        f"Defaults to {_LINE_THICKNESS_DEFAULT}m. Rendered as solid geometry so the "
                        "grid is visible under the default SURFACES_AND_SOLIDS dimensionality most "
                        "viewers use, instead of relying on curve support."
                    ),
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "spacing": {"type": "number"},
                "margin": {"type": "number"},
                "line_thickness": {"type": "number"},
                "extents": {"type": "object"},
                "grid_bounds": {"type": "object"},
                "x_axes": {"type": "array"},
                "y_axes": {"type": "array"},
                "z_axes": {"type": "array"},
                "entities_created": {"type": "object"},
                "schema_limitations": {"type": "string"},
            },
        },
        log_message={
            "info": {
                "en": "3D reference grid (three IfcGrid planes) was inserted into the IFC file."
            },
            "debug_entry": {
                "en": "Computing extents and inserting the 3D reference grid."
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ifcopenshell

        ifc_path = Path(str(context.get_parameter_value("ifc_path"))).expanduser().resolve()
        if not ifc_path.is_file():
            raise ValueError(f"IFC file does not exist: {ifc_path}")

        spacing_override = (
            context.get_parameter_value("spacing") if context.has_parameter("spacing") else None
        )
        margin_override = (
            context.get_parameter_value("margin") if context.has_parameter("margin") else None
        )
        storey_global_id = (
            str(context.get_parameter_value("storey_global_id"))
            if context.has_parameter("storey_global_id")
            else None
        )
        line_thickness_override = (
            context.get_parameter_value("line_thickness")
            if context.has_parameter("line_thickness")
            else None
        )

        spacing_value = None if spacing_override is None else float(spacing_override)
        margin_value = None if margin_override is None else float(margin_override)
        line_thickness = (
            _LINE_THICKNESS_DEFAULT if line_thickness_override is None else float(line_thickness_override)
        )
        if spacing_value is not None and spacing_value <= 0:
            raise ValueError("'spacing' must be greater than zero.")
        if margin_value is not None and margin_value < 0:
            raise ValueError("'margin' must be zero or greater.")
        if line_thickness <= 0:
            raise ValueError("'line_thickness' must be greater than zero.")

        model = ifcopenshell.open(str(ifc_path))
        existing_names = {getattr(grid, "Name", None) for grid in model.by_type("IfcGrid")}
        conflicting = existing_names & GRID_NAMES
        if conflicting:
            raise ValueError(
                f"{sorted(conflicting)} already exist in {ifc_path}. Remove them before regenerating the grid."
            )

        extents = ModelExtentsService.compute(model)
        spacing = spacing_value or ScaleMath.nice_step(
            min(extents.x_range, extents.y_range) / 5.0
        )
        margin = spacing if margin_value is None else margin_value

        x_lo, x_hi = extents.min_x - margin, extents.max_x + margin
        y_lo, y_hi = extents.min_y - margin, extents.max_y + margin
        z_lo, z_hi = 0.0, max(0.0, extents.max_z) + margin

        x_positions = axis_positions(x_lo, x_hi, spacing)
        y_positions = axis_positions(y_lo, y_hi, spacing)
        z_positions = axis_positions(z_lo, z_hi, spacing)
        x_tags: List[str] = latin_tags(len(x_positions))
        y_tags: List[str] = ordinal_tags(len(y_positions))
        z_tags: List[str] = greek_tags(len(z_positions))

        ctx_repo = RepresentationContextRepository(model)
        body_context = ctx_repo.get_body()
        annotation_context = ctx_repo.get_annotation(body_context)
        storey = SpatialContainerRepository(model).get_storey(storey_global_id)

        entities_created = new_entity_counter()
        xy_frame, xz_frame, yz_frame = standard_3plane_frames(x_lo, y_lo)

        build_reference_grid_plane(
            model=model,
            body_context=body_context,
            annotation_context=annotation_context,
            storey=storey,
            name=GRID_NAME_XY,
            placement=xy_frame,
            u_tags=x_tags,
            u_positions=x_positions,
            v_tags=y_tags,
            v_positions=y_positions,
            u_span=(x_lo, x_hi),
            v_span=(y_lo, y_hi),
            line_thickness=line_thickness,
            entities_created=entities_created,
        )
        build_reference_grid_plane(
            model=model,
            body_context=body_context,
            annotation_context=annotation_context,
            storey=storey,
            name=GRID_NAME_XZ,
            placement=xz_frame,
            u_tags=x_tags,
            u_positions=x_positions,
            v_tags=z_tags,
            v_positions=z_positions,
            u_span=(x_lo, x_hi),
            v_span=(z_lo, z_hi),
            line_thickness=line_thickness,
            entities_created=entities_created,
        )
        build_reference_grid_plane(
            model=model,
            body_context=body_context,
            annotation_context=annotation_context,
            storey=storey,
            name=GRID_NAME_YZ,
            placement=yz_frame,
            u_tags=y_tags,
            u_positions=y_positions,
            v_tags=z_tags,
            v_positions=z_positions,
            u_span=(y_lo, y_hi),
            v_span=(z_lo, z_hi),
            line_thickness=line_thickness,
            entities_created=entities_created,
        )

        AtomicFileWriter.write(ifc_path, lambda tmp: model.write(str(tmp)))

        return {
            "ifc_path": str(ifc_path),
            "spacing": spacing,
            "margin": margin,
            "line_thickness": line_thickness,
            "extents": {
                "min_x": extents.min_x,
                "max_x": extents.max_x,
                "min_y": extents.min_y,
                "max_y": extents.max_y,
                "min_z": extents.min_z,
                "max_z": extents.max_z,
            },
            "grid_bounds": {
                "x": [x_lo, x_hi],
                "y": [y_lo, y_hi],
                "z": [z_lo, z_hi],
            },
            "x_axes": x_tags,
            "y_axes": y_tags,
            "z_axes": z_tags,
            "entities_created": entities_created,
            "schema_limitations": (
                "All three planes (XY, XZ, YZ) are real IfcGrid instances with genuine "
                "UAxes/VAxes -- IfcGrid's ObjectPlacement is a full IfcAxis2Placement3D, not "
                "restricted to the horizontal plane, so the XZ/YZ grids are simply rotated "
                "90deg about a principal axis rather than modelled as an annotation "
                "workaround. Every IfcGridAxis.AxisCurve is a real IfcPolyline in that grid's "
                "own local (u, v) plane, as the schema requires. Each line is additionally "
                "drawn as a thin IfcExtrudedAreaSolid rod (SweptSolid body representation), "
                "because most geometry pipelines (ifcopenshell.geom.iterator included) "
                "default to dimensionality=SURFACES_AND_SOLIDS and silently skip curve-only "
                "representations -- with the rods, all three grids render under that default "
                "with no viewer-side setting needed. The per-axis IfcTextLiteral tags are the "
                "one remaining IfcAnnotation usage; whether the alphanumeric label itself is "
                "visible in the 3D view still depends on viewer support for IfcTextLiteral, "
                "but the tag data (and the AxisTag on every IfcGridAxis) is present regardless."
            ),
        }
