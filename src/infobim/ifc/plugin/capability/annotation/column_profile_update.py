"""Mutate the Body/SweptSolid cross-section of an existing ``IfcColumn``.

This capability performs a *targeted* mutation of only the parametric
profile: given an existing ``IfcColumn`` it swaps the ``SweptArea`` of every
``IfcExtrudedAreaSolid`` in the column's Body/SweptSolid representation for
a freshly-built profile of the caller-chosen shape, **preserving** the
``Position``, ``Depth`` and ``ExtrudedDirection`` of each body solid.
Structural attachments, storey containment, ``IfcRelDefinesByType`` linkage,
owner-history, Axis representation, FootPrint representation, and any
existing IfcPropertySets all remain unchanged -- exactly what you'd expect
from a "resize the column's section only" operation.

Supported section types (match :class:`infobim.ifc.adapter.profile_mutation.ProfileSpec`):

* ``RECTANGLE``            -- ``IfcRectangleProfileDef``            (width, depth)
* ``RECTANGLE_HOLLOW``     -- ``IfcRectangleHollowProfileDef``     (+ wall_thickness)
* ``CIRCLE``               -- ``IfcCircleProfileDef``              (outer_diameter)
* ``CIRCLE_HOLLOW``        -- ``IfcCircleHollowProfileDef``        (inner_diameter *or* wall_thickness)

The target column is **always** identified by ``column_global_id``.  This
is deliberate: columns are usually cloned by the dozens in structural
projects, so a Name-based match would silently batch-update the wrong set;
GlobalId gives single-target semantics and unambiguous audit trails.

Profile validation is delegated entirely to :class:`ProfileSpec`.  The
dataclass validates itself on construction (including hollow-wall
feasibility checks) so the capability body only has to parse CLI input
values into a ``ProfileSpec`` and hand it to :class:`IfcProfileMutator`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from infobim.ifc.adapter.profile_mutation import (
    IfcProfileMutator,
    ProfileSpec,
)
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.atomic_file import AtomicFileWriter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class ColumnProfileUpdateCapability(TransactionCapability):
    """Resize the Body cross-section of an existing ``IfcColumn`` in place."""

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.annotation.column_profile_update",
        version="1.0.0",
        name="Column Profile Update",
        description=(
            "Replace the Body/SweptSolid cross-section of an existing IfcColumn with "
            "a freshly-built parametric profile.  The target column is identified by "
            "GlobalId (single-target semantics).  Position, Depth, ExtrudedDirection, "
            "storey containment, property sets, owner history and all non-Body "
            "representations (Axis, FootPrint, ...) are preserved exactly as they "
            "were before the call.  Four profile types are supported: RECTANGLE "
            "(width + depth), RECTANGLE_HOLLOW (width + depth + wall_thickness), "
            "CIRCLE (outer_diameter) and CIRCLE_HOLLOW (outer_diameter plus either "
            "inner_diameter or wall_thickness).  ProfileSpec validates dimensional "
            "feasibility up-front (hollow wall must be strictly positive and "
            "strictly less than half the outer minor axis, inner bore must be "
            "strictly smaller than outer diameter, etc.) so the IFC write step "
            "only happens after the inputs are known-good."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "column", "profile", "mutation", "section"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the existing .ifc file containing the IfcColumn.",
                },
                "column_global_id": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "The unique IfcColumn.GlobalId of the target column. "
                        "Required -- a single column is updated per call."
                    ),
                },
                "profile_type": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "One of: RECTANGLE, RECTANGLE_HOLLOW, CIRCLE, CIRCLE_HOLLOW."
                    ),
                },
                "width": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Required for RECTANGLE / RECTANGLE_HOLLOW: width in metres "
                        "(maps to IfcRectangleProfileDef.XDim)."
                    ),
                },
                "depth": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Required for RECTANGLE / RECTANGLE_HOLLOW: depth in metres "
                        "(maps to IfcRectangleProfileDef.YDim)."
                    ),
                },
                "outer_diameter": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Required for CIRCLE / CIRCLE_HOLLOW: outer circle diameter "
                        "in metres."
                    ),
                },
                "inner_diameter": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "CIRCLE_HOLLOW only: inner bore diameter in metres. "
                        "Mutually exclusive with wall_thickness (one of the two is "
                        "required for hollow circles)."
                    ),
                },
                "wall_thickness": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Wall thickness in metres.  Required for RECTANGLE_HOLLOW; "
                        "for CIRCLE_HOLLOW you can pass either this or inner_diameter."
                    ),
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "column_global_id": {"type": "string"},
                "column_name": {"type": "string"},
                "column_object_type": {"type": ["string", "null"]},
                "old_profile": {"type": "object"},
                "new_profile": {"type": "object"},
                "solids_updated": {"type": "integer"},
                "preserved_depths": {"type": "array"},
                "preserved_positions_count": {"type": "integer"},
                "changed": {"type": "boolean"},
                "entities_created": {"type": "object"},
            },
        },
        log_message={
            "info": {
                "en": "The Body/SweptSolid cross-section of the IfcColumn was updated.",
                "pt-br": "A seção transversal Body/SweptSolid do IfcColumn foi atualizada.",
            },
            "debug_entry": {
                "en": "Building a ProfileSpec, inspecting the IfcColumn's current Body representation, and replacing its SweptArea profiles.",
                "pt-br": "Construindo um ProfileSpec, inspecionando a representação Body atual da IfcColumn e substituindo seus perfis SweptArea.",
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

        column_global_id = str(context.get_parameter_value("column_global_id")).strip()
        if not column_global_id:
            raise ValueError("'column_global_id' is required.")

        # ── Build ProfileSpec (self-validating dataclass) ────────────────────
        width: Optional[float] = (
            float(context.get_parameter_value("width"))
            if context.has_parameter("width")
            else None
        )
        depth: Optional[float] = (
            float(context.get_parameter_value("depth"))
            if context.has_parameter("depth")
            else None
        )
        outer_diameter: Optional[float] = (
            float(context.get_parameter_value("outer_diameter"))
            if context.has_parameter("outer_diameter")
            else None
        )
        inner_diameter: Optional[float] = (
            float(context.get_parameter_value("inner_diameter"))
            if context.has_parameter("inner_diameter")
            else None
        )
        wall_thickness: Optional[float] = (
            float(context.get_parameter_value("wall_thickness"))
            if context.has_parameter("wall_thickness")
            else None
        )
        profile_type_value = str(context.get_parameter_value("profile_type")).strip()
        spec = ProfileSpec(
            profile_type=profile_type_value,
            width=width,
            depth=depth,
            outer_diameter=outer_diameter,
            inner_diameter=inner_diameter,
            wall_thickness=wall_thickness,
        )

        # ── Open model and locate the column ─────────────────────────────────
        model = ifcopenshell.open(str(ifc_path))

        # The canonical ifcopenshell way to get a single occurrence by GUID:
        target = model.by_guid(column_global_id)
        if target is None:
            raise ValueError(
                f"No IFC element with GlobalId '{column_global_id}' was found."
            )
        if not target.is_a("IfcColumn"):
            raise ValueError(
                f"Element with GlobalId '{column_global_id}' is a "
                f"'{target.is_a()}', not an 'IfcColumn'.  Use the appropriate "
                f"profile-update capability for that element type."
            )

        # ── Mutate profile ───────────────────────────────────────────────────
        entities_created: Dict[str, int] = {}
        mutator = IfcProfileMutator(model, entities_created)
        current_info = mutator.get_current_profile_info(target)

        mutation_report = mutator.apply_profile(target, spec)

        # ── Atomic write ─────────────────────────────────────────────────────
        AtomicFileWriter.write(ifc_path, lambda tmp: model.write(str(tmp)))

        preserved_depths = list(mutation_report.get("preserved_depths", []))
        solids_updated = int(mutation_report.get("solids_updated", 0))

        return {
            "ifc_path": str(ifc_path),
            "column_global_id": column_global_id,
            "column_name": str(getattr(target, "Name", "") or ""),
            "column_object_type": (
                str(getattr(target, "ObjectType", None) or None) or None
            ),
            "old_profile": current_info,
            "new_profile": mutation_report.get("new_profile", {}),
            "solids_updated": solids_updated,
            "preserved_depths": preserved_depths,
            "preserved_positions_count": int(
                mutation_report.get("preserved_positions_count", 0)
            ),
            "changed": True,
            "entities_created": entities_created,
        }
