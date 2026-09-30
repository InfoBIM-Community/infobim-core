from math import isfinite
from numbers import Real
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.geometry_state import GeometricProductState
from infobim.ifc.adapter.schema_identifier import IfcSchemaIdentifier
from infobim.ifc.domain.exception.creation import (
    GeometryDefinitionInvalidError,
    IfcCreationError,
)
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.domain.port.geometry import GeometryCreateResponsibilityPort


class CylinderGeometryCreateCapability(
    TransformationCapability,
    GeometryCreateResponsibilityPort,
):
    """Create an ``IfcRightCircularCylinder`` from its intrinsic parameters.

    The cylinder is positioned by its base-center point and oriented by the
    axis direction supplied by the geometry definition. Height and radius are
    positive lengths; reversing the cylinder is expressed by reversing the
    direction vector, not by a negative height.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.transformation.geometry.cylinder",
        version="0.1.0",
        name="Cylinder Geometry Creation",
        description="Create a right circular cylinder geometry.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometry", "cylinder"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "geometry": {
                    "type": "object",
                    "required": True,
                    "description": "The geometry definition selected by the chain.",
                },
                "position": {
                    "type": "object",
                    "required": True,
                    "description": "The base-center position of the cylinder.",
                },
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the product belongs to.",
                },
                "title": {
                    "type": "string",
                    "required": True,
                    "description": "The title of the product being assembled.",
                },
            },
        },
        log_message={
            "info": {"en": "The IFC cylinder geometry was created."},
            "debug_entry": {"en": "Creating the IFC cylinder geometry."},
        },
    )

    RADIUS_KEY: ClassVar[str] = "radius"
    HEIGHT_KEY: ClassVar[str] = "height"
    DIRECTION_KEYS: ClassVar[Tuple[str, str, str]] = (
        "direction_x",
        "direction_y",
        "direction_z",
    )
    KIND: ClassVar[str] = GeometryDefinition.CYLINDER_KIND
    KIND_KEY: ClassVar[str] = GeometryDefinition.KIND_KEY
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    TITLE_KEY: ClassVar[str] = "title"
    GEOMETRY_KEY: ClassVar[str] = "geometry"
    POSITION_KEY: ClassVar[str] = "position"
    STEP_ELEMENTS_KEY: ClassVar[str] = "step_elements"
    GEOMETRY_ITEM_KEY: ClassVar[str] = "geometry_item"
    STATE_PATH_KEY: ClassVar[str] = "geometry_state_path"
    IFC_SCHEMA: ClassVar[str] = "IFC4"
    IFC_SCHEMA_FAMILIES: ClassVar[Tuple[str, ...]] = ("IFC4", "IFC4X3")

    def label(self, lang: str = "en") -> str:
        return "Cylinder Geometry Creation"

    def description(self, lang: str = "en") -> str:
        return "Create a right circular cylinder geometry."

    def can_handle(
        self,
        context: CliContextPort,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self._states_this_kind(extra_data):
            return False

        parameters = self._validated_parameters(extra_data)
        if parameters is None:
            return False
        return self._context_model_is_supported(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ifcopenshell

        definition: GeometryDefinition = self._definition(context)
        parameters = self._validated_parameters(dict(definition.parameters))
        if parameters is None:
            raise GeometryDefinitionInvalidError(
                "Cylinder geometry requires a positive finite radius and height "
                "and a finite, non-zero direction vector."
            )

        radius, height, direction = parameters
        position: Dict[str, float] = self._position(context)
        model: Any = ifcopenshell.file(schema=self._schema_identifier(context))

        origin: Any = model.create_entity(
            "IfcCartesianPoint",
            Coordinates=(0.0, 0.0, 0.0),
        )
        axis: Any = model.create_entity(
            "IfcDirection",
            DirectionRatios=direction,
        )
        placement: Any = model.create_entity(
            "IfcAxis2Placement3D",
            Location=origin,
            Axis=axis,
        )
        cylinder: Any = model.create_entity(
            "IfcRightCircularCylinder",
            Position=placement,
            Height=height,
            Radius=radius,
        )

        created: List[Any] = [origin, axis, placement, cylinder]
        step_elements: List[str] = [str(entity.id()) for entity in created]
        geometry_item: str = str(cylinder.id())

        state_path: Path = GeometricProductState.write(
            model,
            GeometricProductState.path_of(
                self._container_path(context),
                self._title(context),
                GeometricProductState.GEOMETRY_FILE_NAME,
            ),
        )

        context.set_parameter_value(self.STEP_ELEMENTS_KEY, step_elements)
        context.set_parameter_value(self.GEOMETRY_ITEM_KEY, geometry_item)

        return {
            self.STEP_ELEMENTS_KEY: step_elements,
            self.GEOMETRY_ITEM_KEY: geometry_item,
            self.STATE_PATH_KEY: str(state_path),
        }

    @classmethod
    def _states_this_kind(cls, extra_data: Optional[Dict[str, Any]]) -> bool:
        """
        Report whether the run's geometry is the primitive this creates.

        Answering by the measurements alone would answer for another
        primitive's: a cylinder is measured by a radius as much as a
        sphere is, so whichever responsibility's turn came first would
        create the wrong solid. The kind is what says which one it is,
        and a run that states none states no primitive at all.
        """
        if extra_data is None or cls.KIND_KEY not in extra_data:
            return False

        return extra_data[cls.KIND_KEY] == cls.KIND

    @classmethod
    def _definition(cls, context: CliContextPort) -> GeometryDefinition:
        if not context.has_parameter(cls.GEOMETRY_KEY):
            raise GeometryDefinitionInvalidError(
                "No geometry definition is present in the command context."
            )

        value: Any = context.get_parameter_value(cls.GEOMETRY_KEY)
        if isinstance(value, GeometryDefinition):
            return value
        if isinstance(value, dict):
            definition: Optional[GeometryDefinition] = GeometryDefinition.from_dict(
                value
            )
            if definition is not None:
                return definition

        raise GeometryDefinitionInvalidError(
            "The geometry definition in the command context is invalid."
        )

    @classmethod
    def _validated_parameters(
        cls,
        data: Optional[Dict[str, Any]],
    ) -> Optional[Tuple[float, float, Tuple[float, float, float]]]:
        if data is None:
            return None

        required = (cls.RADIUS_KEY, cls.HEIGHT_KEY, *cls.DIRECTION_KEYS)
        if not all(key in data for key in required):
            return None

        radius = cls._positive_number(data[cls.RADIUS_KEY])
        height = cls._positive_number(data[cls.HEIGHT_KEY])
        if radius is None or height is None:
            return None

        direction_values: List[float] = []
        for key in cls.DIRECTION_KEYS:
            numeric = cls._finite_number(data[key])
            if numeric is None:
                return None
            direction_values.append(numeric)

        direction = (
            direction_values[0],
            direction_values[1],
            direction_values[2],
        )
        if direction == (0.0, 0.0, 0.0):
            return None

        return radius, height, direction

    @staticmethod
    def _finite_number(value: Any) -> Optional[float]:
        if isinstance(value, bool) or not isinstance(value, Real):
            return None
        numeric: float = float(value)
        if not isfinite(numeric):
            return None
        return numeric

    @classmethod
    def _positive_number(cls, value: Any) -> Optional[float]:
        numeric = cls._finite_number(value)
        if numeric is None or numeric <= 0.0:
            return None
        return numeric

    @classmethod
    def _position(cls, context: CliContextPort) -> Dict[str, float]:
        value: Any = context.get_parameter_value(cls.POSITION_KEY)
        if not isinstance(value, dict):
            raise IfcCreationError("The geometry position is not defined.")

        position: Dict[str, float] = {}
        for axis in ("x", "y", "z"):
            coordinate: Any = value.get(axis)
            numeric = cls._finite_number(coordinate)
            if numeric is None:
                raise IfcCreationError(
                    f"The position {axis} coordinate must be a finite real number."
                )
            position[axis] = numeric
        return position

    @classmethod
    def _model_path(cls, context: CliContextPort) -> Optional[Path]:
        if not context.has_parameter(cls.IFC_MODEL_PATH_KEY):
            return None
        value: Any = context.get_parameter_value(cls.IFC_MODEL_PATH_KEY)
        if not isinstance(value, str) or not value.strip():
            return None
        return Path(value).expanduser().resolve()

    @classmethod
    def _container_path(cls, context: CliContextPort) -> Path:
        value: Any = context.get_parameter_value(cls.CONTAINER_PATH_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The InfoBIM project is missing from the command context, so "
                "the product being assembled has nowhere to be kept."
            )
        return Path(value).expanduser().resolve()

    @classmethod
    def _title(cls, context: CliContextPort) -> str:
        value: Any = context.get_parameter_value(cls.TITLE_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The product title is missing from the command context, so "
                "the product being assembled cannot be named."
            )
        return value.strip()

    @classmethod
    def _schema_identifier(cls, context: CliContextPort) -> str:
        import ifcopenshell

        model_path: Optional[Path] = cls._model_path(context)
        if model_path is None or not model_path.is_file():
            return cls.IFC_SCHEMA

        model: Any = ifcopenshell.open(str(model_path))
        cls._require_supported_schema(model)
        identifier: Any = getattr(model, "schema_identifier", None)
        if identifier is None:
            identifier = getattr(model, "schema", None)
        if identifier is None:
            return cls.IFC_SCHEMA
        return str(identifier)

    @classmethod
    def _context_model_is_supported(cls, context: CliContextPort) -> bool:
        model_path: Optional[Path] = cls._model_path(context)
        if model_path is None:
            return True
        if not model_path.is_file():
            return False

        try:
            import ifcopenshell

            model: Any = ifcopenshell.open(str(model_path))
            return cls._schema_family(model) in cls.IFC_SCHEMA_FAMILIES
        except Exception:
            return False

    @classmethod
    def _require_supported_schema(cls, model: Any) -> None:
        schema: Optional[str] = cls._schema_family(model)
        if schema not in cls.IFC_SCHEMA_FAMILIES:
            raise IfcCreationError(
                f"Cylinder geometry creation supports the "
                f"{', '.join(cls.IFC_SCHEMA_FAMILIES)} families; the target "
                f"model uses {schema or 'an unknown schema'}."
            )

    @staticmethod
    def _schema_family(model: Any) -> Optional[str]:
        identifier: Any = getattr(model, "schema_identifier", None)
        if identifier is None:
            identifier = getattr(model, "schema", None)
        if identifier is None:
            return None
        return IfcSchemaIdentifier.family_of(str(identifier).upper())
