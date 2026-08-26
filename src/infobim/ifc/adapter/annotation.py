"""Builders for ``IfcAnnotation`` user-visible content.

Currently: ``IfcTextAnnotationBuilder``, which constructs a complete
``IfcAnnotation`` carrying an ``IfcTextLiteral`` — used by per-axis
reference-grid labels, construction callouts, survey markers, etc.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


Point3D = Tuple[float, float, float]


class IfcTextAnnotationBuilder:
    """Construct an ``IfcAnnotation`` hosting one ``IfcTextLiteral``.

    The built annotation is:

    * attached to ``storey`` via ``IfcRelContainedInSpatialStructure``
      (``ifcopenshell.api.spatial.assign_container``),
    * placed in world space via ``edit_object_placement`` applied to a
      4x4 translation matrix,
    * given a caller-controlled ``ObjectType`` so related annotations can
      later be found / removed as a cohort.
    """

    def __init__(
        self,
        model: Any,
        entities_created: Optional[Dict[str, int]] = None,
    ) -> None:
        self._model = model
        self._counter = entities_created

    def _bump(self, key: str) -> None:
        if self._counter is not None:
            self._counter[key] = int(self._counter.get(key, 0)) + 1

    def create_text_label(
        self,
        *,
        annotation_context: Any,
        storey: Any,
        name: str,
        text: str,
        location: Point3D,
        object_type: str = "TEXT_LABEL",
    ) -> Any:
        import ifcopenshell.api.geometry as geometry_api
        import ifcopenshell.api.root as root_api
        import ifcopenshell.api.spatial as spatial_api

        placement = self._model.create_entity(
            "IfcAxis2Placement3D",
            Location=self._model.create_entity(
                "IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0)
            ),
        )
        text_literal = self._model.create_entity(
            "IfcTextLiteral", Literal=text, Placement=placement, Path="RIGHT"
        )
        self._bump("IfcTextLiteral")
        shape_rep = self._model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=annotation_context,
            RepresentationIdentifier="Annotation",
            RepresentationType="Annotation2D",
            Items=[text_literal],
        )
        product_shape = self._model.create_entity(
            "IfcProductDefinitionShape", Representations=[shape_rep]
        )
        annotation = root_api.create_entity(
            self._model,
            ifc_class="IfcAnnotation",
            name=name,
            predefined_type="USERDEFINED",
        )
        annotation.ObjectType = object_type
        annotation.Representation = product_shape
        self._bump("IfcAnnotation")
        spatial_api.assign_container(
            self._model, relating_structure=storey, products=[annotation]
        )
        geometry_api.edit_object_placement(
            self._model,
            product=annotation,
            matrix=(
                (1, 0, 0, location[0]),
                (0, 1, 0, location[1]),
                (0, 0, 1, location[2]),
                (0, 0, 0, 1),
            ),
        )
        return annotation
