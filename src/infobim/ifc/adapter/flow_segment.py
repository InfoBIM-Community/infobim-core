"""IFC builders for straight flow segments (pipe, duct, cable carrier).

``IfcFlowSegment`` is the schema-correct super-type for straight linear
HVAC/plumbing runs; ``IfcPipeSegment`` is the IFC4-concrete subtype for
piping.  This builder keeps the same conventions used by the other
geometry / annotation adapters in this package:

* ``IfcPipeSegment`` is produced via ``ifcopenshell.api.root.create_entity``
  (not ``model.create_entity`` directly) so the instance receives a
  canonical GlobalId and the default owner-history linkage the rest of the
  project expects -- matching the pattern in ``annotation.py``.
* The geometric body is a solid ``IfcExtrudedAreaSolid`` rendered through
  ``IfcSolidBuilder.extruded_circular_rod`` (see ``geometry_builder.py``),
  the same low-level approach used for grid rods so viewers defaulting to
  SURFACES_AND_SOLIDS render both feature types identically.
* Spatial containment uses ``ifcopenshell.api.spatial.assign_container``
  and placement translation uses ``ifcopenshell.api.geometry.edit_object_placement``
  -- again identical to ``IfcTextAnnotationBuilder.create_text_label``.
* Optional material linkage uses ``ifcopenshell.api.material`` helpers
  (when the module is available) instead of building ``IfcRelAssociatesMaterial``
  by hand; this keeps foreign-key ordering consistent with the rest of the
  IFC writing pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from infobim.ifc.adapter.geometry_builder import IfcSolidBuilder


Point3D = Tuple[float, float, float]


class IfcFlowSegmentBuilder:
    """Create ``IfcPipeSegment`` entities with solid swept bodies.

    The builder is deliberately small: one straight pipe per call, single
    direction, circular cross-section.  Fittings, reducers, branches and
    multi-segment runs are intentionally out of scope -- they belong in a
    dedicated HVAC adapter, not in a positioning helper.
    """

    def __init__(
        self,
        model: Any,
        entities_created: Optional[Dict[str, int]] = None,
    ) -> None:
        self._model = model
        self._counter = entities_created
        self._solid_builder = IfcSolidBuilder(model, entities_created)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _bump(self, key: str) -> None:
        if self._counter is not None:
            self._counter[key] = int(self._counter.get(key, 0)) + 1

    # ── Public single-shot build ─────────────────────────────────────────────

    def create_pipe_segment(
        self,
        *,
        body_context: Any,
        start: Point3D,
        end: Point3D,
        outer_diameter: float,
        inner_diameter: Optional[float] = None,
        storey: Optional[Any] = None,
        name: str = "Pipe Segment",
        description: str = "",
        object_type: Optional[str] = None,
        material_name: Optional[str] = None,
    ) -> Any:
        """Create a single ``IfcPipeSegment`` anchored to ``body_context``.

        Args:
            body_context: the ``Body`` ``IfcGeometricRepresentationSubContext``
                returned by ``RepresentationContextRepository.get_body()``.
            start: world-space start point (in metres).
            end: world-space end point (in metres).
            outer_diameter: pipe outer diameter in metres (positive float).
            inner_diameter: optional inner free-bore diameter in metres.  A
                hollow ``IfcCircleHollowProfileDef`` is used when the value
                is strictly between 0 and ``outer_diameter``; otherwise a
                plain solid circular rod is produced.
            storey: optional ``IfcBuildingStorey`` used as the spatial host
                via ``assign_container`` (same call used in the annotation
                builder).
            name: value for ``IfcPipeSegment.Name``.
            description: value for ``IfcPipeSegment.Description``.
            object_type: optional user-defined tag stored in
                ``IfcPipeSegment.ObjectType``.  The recommendation is to
                set it so future capabilities can quickly find all pipes
                created by this workflow without regex-scanning ``Name``.
            material_name: optional label written into a lightweight
                ``IfcMaterial`` assigned via ``ifcopenshell.api.material``
                when available; purely semantic, has no geometric effect.
        """
        import ifcopenshell.api.geometry as geometry_api
        import ifcopenshell.api.root as root_api
        import ifcopenshell.api.spatial as spatial_api

        if float(outer_diameter) <= 0:
            raise ValueError("'outer_diameter' must be greater than zero.")

        solid = self._solid_builder.extruded_circular_rod(
            start, end, outer_diameter, inner_diameter
        )
        body_rep = self._model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=body_context,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=[solid],
        )
        self._bump("IfcShapeRepresentation")
        product_shape = self._model.create_entity(
            "IfcProductDefinitionShape",
            Representations=[body_rep],
        )
        self._bump("IfcProductDefinitionShape")

        segment = root_api.create_entity(
            self._model,
            ifc_class="IfcPipeSegment",
            name=name,
            description=description or None,
        )
        if object_type is not None:
            segment.ObjectType = str(object_type)
        segment.Representation = product_shape
        self._bump("IfcPipeSegment")

        # Placement: the swept-solid body already contains the full run via
        # Depth, so we only need to translate the product's origin to the
        # segment start point -- no rotation beyond what the swept placement
        # already applies.
        geometry_api.edit_object_placement(
            self._model,
            product=segment,
            matrix=(
                (1.0, 0.0, 0.0, start[0]),
                (0.0, 1.0, 0.0, start[1]),
                (0.0, 0.0, 1.0, start[2]),
                (0.0, 0.0, 0.0, 1.0),
            ),
        )

        if material_name:
            try:
                import ifcopenshell.api.material as material_api

                material = material_api.add_material(
                    self._model, name=str(material_name)
                )
                self._bump("IfcMaterial")
                material_api.assign_material(
                    self._model,
                    products=[segment],
                    material=material,
                )
                self._bump("IfcRelAssociatesMaterial")
            except Exception:  # pragma: no cover - material linkage is decorative
                pass

        if storey is not None:
            spatial_api.assign_container(
                self._model,
                relating_structure=storey,
                products=[segment],
            )

        return segment
