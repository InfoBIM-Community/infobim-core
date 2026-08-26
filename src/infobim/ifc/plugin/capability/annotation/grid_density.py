"""Open or close the 3D reference grid inserted by ReferenceGridCapability.

"Closing" the grid means shrinking the spacing between axes (more, denser
axes); "opening" it means growing the spacing (fewer, sparser axes).

Interpretation of the request, spelled out because the sign convention is
otherwise easy to misread: ``steps`` is a *signed* integer, default 5.

- steps > 0  -> "fechar" (close): each unit shrinks the area of one grid
  cell by 10% (cell area = spacing^2, so spacing itself shrinks by
  sqrt(0.9) per step). More, smaller cells fit in the same extent, so the
  axis count goes up.
- steps < 0  -> "abrir" (open): the same formula, applied in reverse
  (0.9^steps > 1 when steps is negative) -- cell area grows 1/0.9 = ~11.1%
  per unit, spacing grows, and the axis count goes down.
- steps == 0 -> no-op (grid rebuilt identically).

Margin (the gap beyond the model's bounding box, normally one grid module)
scales by the same linear factor as spacing, so the "one module" margin
convention from ReferenceGridCapability stays consistent after resizing.

Requires the grid to already exist (run ReferenceGridCapability first);
it is removed and rebuilt in place, never left duplicated. Never touches
any element outside the reference grid itself.

Delegates geometric primitives, placement matrices, context lookups,
the single-plane builder, the current-* read-backs, the teardown step
and the atomic writer to the dedicated ``infobim.ifc.adapter.*`` /
``ontobdc.shared.adapter.*`` modules, so the two grid capabilities do
not contain parallel copies of the same low-level code.
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
    current_line_thickness,
    current_margin,
    current_spacing,
    greek_tags,
    latin_tags,
    new_entity_counter,
    ordinal_tags,
    remove_existing_reference_grids,
    standard_3plane_frames,
)
from infobim.ifc.adapter.representation import RepresentationContextRepository
from infobim.ifc.adapter.spatial import SpatialContainerRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.atomic_file import AtomicFileWriter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


_DEFAULT_STEPS = 5
_MIN_SPACING = 0.01


class GridDensityAdjustedCapability(TransactionCapability):
    """Close (denser) or open (sparser) the existing 3D reference grid by discrete 10%-area steps."""

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.annotation.grid_density_adjusted",
        version="1.0.0",
        name="Grid Density Adjusted",
        description=(
            "Close or open the existing 3D reference grid (see ReferenceGridCapability) by "
            "a discrete number of 10%-per-unit steps applied to each grid cell's area. "
            "Positive steps close the grid (smaller cells, more axes); negative steps open "
            "it (larger cells, fewer axes); default is 5 (close). The grid is removed and "
            "rebuilt in place at the new spacing -- it must already exist."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "grid", "reference", "positioning", "density"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the existing .ifc file whose reference grid should be resized.",
                },
                "steps": {
                    "type": "integer",
                    "required": False,
                    "description": (
                        f"Signed discrete step count, default {_DEFAULT_STEPS}. Positive closes the "
                        "grid (cell area x0.9 per step, so spacing xsqrt(0.9) per step, more axes); "
                        "negative opens it (cell area /0.9 per step, spacing /sqrt(0.9) per step, "
                        "fewer axes); 0 rebuilds unchanged."
                    ),
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "steps": {"type": "integer"},
                "direction": {"type": "string"},
                "area_factor": {"type": "number"},
                "spacing_factor": {"type": "number"},
                "previous_spacing": {"type": "number"},
                "new_spacing": {"type": "number"},
                "previous_margin": {"type": "number"},
                "new_margin": {"type": "number"},
                "line_thickness": {"type": "number"},
                "extents": {"type": "object"},
                "grid_bounds": {"type": "object"},
                "x_axes": {"type": "array"},
                "y_axes": {"type": "array"},
                "z_axes": {"type": "array"},
                "entities_removed": {"type": "object"},
                "entities_created": {"type": "object"},
            },
        },
        log_message={
            "info": {
                "en": "The 3D reference grid was rebuilt at a new spacing (closed or opened)."
            },
            "debug_entry": {
                "en": "Computing the new grid spacing and rebuilding the reference grid."
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

        steps_value = (
            context.get_parameter_value("steps") if context.has_parameter("steps") else None
        )
        steps = _DEFAULT_STEPS if steps_value is None else int(steps_value)

        model = ifcopenshell.open(str(ifc_path))
        existing_names = {getattr(grid, "Name", None) for grid in model.by_type("IfcGrid")}
        if not (existing_names & GRID_NAMES):
            raise ValueError(
                f"No reference grid found in {ifc_path}. Run ReferenceGridCapability first."
            )

        extents = ModelExtentsService.compute(
            model,
            exclude_object_types=[GRID_LABEL_OBJECT_TYPE],
        )

        previous_spacing = current_spacing(model, GRID_NAME_XY)
        previous_margin = current_margin(model, extents, GRID_NAME_XY)
        line_thickness = current_line_thickness(model, GRID_NAME_XY)

        area_factor = 0.9 ** steps
        spacing_factor = area_factor ** 0.5
        new_spacing = previous_spacing * spacing_factor
        new_margin = previous_margin * spacing_factor

        if new_spacing < _MIN_SPACING:
            raise ValueError(
                f"'steps'={steps} would shrink spacing to {new_spacing:.4f}m, below the "
                f"{_MIN_SPACING}m floor. Use fewer positive steps."
            )

        ctx_repo = RepresentationContextRepository(model)
        body_context = ctx_repo.get_body()
        annotation_context = ctx_repo.get_annotation(body_context)
        try:
            storey = SpatialContainerRepository(model).infer_storey_from_grid(GRID_NAME_XY)
        except ValueError:
            storey = SpatialContainerRepository(model).get_storey()

        entities_removed = remove_existing_reference_grids(model)

        x_lo, x_hi = extents.min_x - new_margin, extents.max_x + new_margin
        y_lo, y_hi = extents.min_y - new_margin, extents.max_y + new_margin
        z_lo, z_hi = 0.0, max(0.0, extents.max_z) + new_margin

        x_positions = axis_positions(x_lo, x_hi, new_spacing)
        y_positions = axis_positions(y_lo, y_hi, new_spacing)
        z_positions = axis_positions(z_lo, z_hi, new_spacing)
        x_tags: List[str] = latin_tags(len(x_positions))
        y_tags: List[str] = ordinal_tags(len(y_positions))
        z_tags: List[str] = greek_tags(len(z_positions))

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

        if steps > 0:
            direction = "fechar"
        elif steps < 0:
            direction = "abrir"
        else:
            direction = "unchanged"

        return {
            "ifc_path": str(ifc_path),
            "steps": steps,
            "direction": direction,
            "area_factor": area_factor,
            "spacing_factor": spacing_factor,
            "previous_spacing": previous_spacing,
            "new_spacing": new_spacing,
            "previous_margin": previous_margin,
            "new_margin": new_margin,
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
            "entities_removed": entities_removed,
            "entities_created": entities_created,
        }
