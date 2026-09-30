import re
from typing import Any, ClassVar, Dict, List, Tuple, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.adapter.target_model import IfcTargetModelReader
from infobim.ifc.adapter.creation_definition import (
    IfcCreationDefinition,
    KindRepresentationCreationDefinition,
)
from infobim.ifc.plugin.machine.geometric_product_create.machine import (
    GeometricProductCreateStateTransitionHandler,
)


class IfcElementsCreatedCapability(TransformationCapability):
    """
    Create one IFC element at each captured point.

    The class, predefined type and geometry come from the kind
    representation the term resolved to. The target model is the one the
    run names under ``ifc_model_path``. Each point is one run of the geometric product creation machine,
    which owns every IFC step; this capability only prepares each run and
    collects the element it federated.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "ifc_elements_created"
        ),
        version="0.1.0",
        name="IFC Elements Created",
        description=(
            "Create one IFC element of the resolved kind representation at "
            "each captured point, through the geometric product creation "
            "machine."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "points"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_model_path": {"type": "string", "required": True},
                "captured_points": {"type": list, "required": True},
                "ontology_term_resolution": {"type": "object", "required": True},
                "kind_representations": {"type": "object", "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_model_path": {"type": "string"},
                "ifc_elements": {"type": "array"},
                "created_count": {"type": "integer"},
            },
        },
        log_message={
            "info": {"en": "IFC elements were created at the captured points."},
            "debug_entry": {"en": "Creating IFC elements at the captured points."},
        },
    )

    POINTS_KEY: ClassVar[str] = "captured_points"
    RESOLUTION_KEY: ClassVar[str] = "ontology_term_resolution"
    REPRESENTATIONS_KEY: ClassVar[str] = "kind_representations"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    ELEMENTS_KEY: ClassVar[str] = "ifc_elements"
    CREATED_COUNT_KEY: ClassVar[str] = "created_count"

    TITLE_KEY: ClassVar[str] = "title"
    GEOMETRY_KEY: ClassVar[str] = "geometry"
    IFC_CLASS_KEY: ClassVar[str] = "ifc_class"
    PREDEFINED_TYPE_KEY: ClassVar[str] = "ifc_predefined_type"
    FEDERATED_PRODUCT_KEY: ClassVar[str] = "federated_product"
    AXES: ClassVar[Tuple[str, str, str]] = ("x", "y", "z")
    PLANE_Z: ClassVar[float] = 0.0
    RUN_KEYS: ClassVar[Tuple[str, ...]] = (
        TITLE_KEY,
        GEOMETRY_KEY,
        IFC_CLASS_KEY,
        PREDEFINED_TYPE_KEY,
    ) + AXES

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        points: List[Tuple[float, float]] = self._points(context)
        definition: IfcCreationDefinition = KindRepresentationCreationDefinition.of(
            context.get_parameter_value(self.RESOLUTION_KEY),
            context.get_parameter_value(self.REPRESENTATIONS_KEY),
        )
        model_path: Path = Path(
            RequiredParameter.of(context, self.IFC_MODEL_PATH_KEY)
        ).expanduser().resolve()

        geometry: Dict[str, Any] = definition.geometry(
            IfcTargetModelReader.metres_per_length_unit(model_path)
        ).to_dict()
        first_index: int = self._next_index(model_path, definition.title_base)

        elements: List[Dict[str, Any]] = []
        try:
            index: int
            x: float
            y: float
            for index, (x, y) in enumerate(points, start=first_index):
                elements.append(
                    self._create(context, definition, geometry, index, x, y)
                )
        finally:
            key: str
            for key in self.RUN_KEYS:
                context.delete_parameter(key)

        context.set_parameter_value(self.ELEMENTS_KEY, elements)
        context.set_parameter_value(self.CREATED_COUNT_KEY, len(elements))
        return {
            self.IFC_MODEL_PATH_KEY: str(model_path),
            self.ELEMENTS_KEY: elements,
            self.CREATED_COUNT_KEY: len(elements),
        }

    def _create(
        self,
        context: CliContextPort,
        definition: IfcCreationDefinition,
        geometry: Dict[str, Any],
        index: int,
        x: float,
        y: float,
    ) -> Dict[str, Any]:
        """Run the creation machine once, for the product at one point."""
        context.set_parameter_value(self.TITLE_KEY, f"{definition.title_base} {index}")
        context.set_parameter_value(self.GEOMETRY_KEY, geometry)
        context.set_parameter_value(self.IFC_CLASS_KEY, definition.ifc_class)
        if definition.predefined_type is None:
            context.delete_parameter(self.PREDEFINED_TYPE_KEY)
        else:
            context.set_parameter_value(
                self.PREDEFINED_TYPE_KEY, definition.predefined_type
            )
        coordinates: Dict[str, float] = {"x": x, "y": y, "z": self.PLANE_Z}
        axis: str
        for axis in self.AXES:
            context.set_parameter_value(axis, coordinates[axis])

        GeometricProductCreateStateTransitionHandler(context).execute()

        global_id: Any = context.get_parameter_value(self.FEDERATED_PRODUCT_KEY)
        if not isinstance(global_id, str) or not global_id.strip():
            raise IfcCreationError(
                f"The product created at ({x}, {y}) was not federated into the "
                "project model."
            )

        return {
            "global_id": global_id.strip(),
            "ifc_class": definition.ifc_class,
            "title": f"{definition.title_base} {index}",
            **coordinates,
        }

    @classmethod
    def _points(cls, context: CliContextPort) -> List[Tuple[float, float]]:
        raw_points: Any = context.get_parameter_value(cls.POINTS_KEY)
        if not isinstance(raw_points, list) or not raw_points:
            raise IfcCreationError(
                "No point was captured, so there is no IFC element to create."
            )

        points: List[Tuple[float, float]] = []
        point: Any
        for point in raw_points:
            if not isinstance(point, dict) or set(point) != {"x", "y"}:
                raise IfcCreationError(f"Captured point {point!r} is not an x/y pair.")
            points.append((float(point["x"]), float(point["y"])))
        return points

    @staticmethod
    def _next_index(model_path: Path, title_base: str) -> int:
        """
        Return the first index free for products titled after the base.

        A product's GlobalId is derived from its title, so numbering after
        the products an earlier run created keeps them apart instead of
        updating them.
        """
        pattern: re.Pattern[str] = re.compile(rf"{re.escape(title_base)} (\d+)")
        used: List[int] = [
            int(match.group(1))
            for name in IfcTargetModelReader.product_names(model_path)
            for match in [pattern.fullmatch(name)]
            if match is not None
        ]
        highest: Optional[int] = max(used) if used else None
        return 1 if highest is None else highest + 1
