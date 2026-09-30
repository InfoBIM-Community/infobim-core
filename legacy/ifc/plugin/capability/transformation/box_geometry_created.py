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


class BoxGeometryCreateCapability(
    TransformationCapability,
    GeometryCreateResponsibilityPort,
):
    """Create an ``IfcBlock`` from three signed orthogonal dimensions.

    The responsibility answers for the IFC4 and IFC 4.3 families alike:
    ``IfcCartesianPoint``, ``IfcAxis2Placement3D`` and ``IfcBlock`` are
    declared by both, so a block written into one is the same block
    written into the other. The target is matched by family rather than
    by the reader's identifier, because an addendum such as
    ``IFC4X3_ADD2`` is a revision of IFC 4.3 and not another schema.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.transformation.geometry.box",
        version="0.1.0",
        name="Box Geometry Creation",
        description="Create a rectangular parallelepiped geometry.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometry", "box"],
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
                    "description": "The local position of the geometry.",
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
            "info": {"en": "The IFC box geometry was created."},
            "debug_entry": {"en": "Creating the IFC box geometry."},
        },
    )

    DIMENSION_KEYS: ClassVar[Tuple[str, str, str]] = (
        "x_length",
        "y_length",
        "z_length",
    )
    KIND: ClassVar[str] = GeometryDefinition.BOX_KIND
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
        return "Box Geometry Creation"

    def description(self, lang: str = "en") -> str:
        return "Create a rectangular parallelepiped geometry."

    def can_handle(
        self,
        context: CliContextPort,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self._states_this_kind(extra_data):
            return False

        dimensions: Optional[Tuple[float, float, float]] = (
            self._validated_dimensions(extra_data)
        )
        if dimensions is None:
            return False
        if not self._context_model_is_supported(context):
            return False

        x_length, y_length, z_length = dimensions
        return x_length * y_length * z_length != 0.0

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ifcopenshell

        definition: GeometryDefinition = self._definition(context)
        dimensions: Optional[Tuple[float, float, float]] = (
            self._validated_dimensions(dict(definition.parameters))
        )
        if dimensions is None:
            raise GeometryDefinitionInvalidError(
                "Box geometry requires finite, non-zero real values for "
                "x_length, y_length and z_length."
            )

        position: Dict[str, float] = self._position(context)
        # The block is created in a file of its own, never in the model the
        # project federates: a representation item is not rooted, so a block
        # written into the model before a product owns it is geometry nobody
        # can address again. The schema is the target model's, so what is
        # assembled here merges into it unchanged.
        model: Any = ifcopenshell.file(schema=self._schema_identifier(context))

        x_length, y_length, z_length = dimensions
        origin: Any = model.create_entity(
            "IfcCartesianPoint",
            Coordinates=(
                position["x"] + min(0.0, x_length),
                position["y"] + min(0.0, y_length),
                position["z"] + min(0.0, z_length),
            ),
        )
        placement: Any = model.create_entity(
            "IfcAxis2Placement3D",
            Location=origin,
        )
        block: Any = model.create_entity(
            "IfcBlock",
            Position=placement,
            XLength=abs(x_length),
            YLength=abs(y_length),
            ZLength=abs(z_length),
        )

        created: List[Any] = [origin, placement, block]
        step_elements: List[str] = [str(entity.id()) for entity in created]
        geometry_item: str = str(block.id())

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
    def _validated_dimensions(
        cls,
        data: Optional[Dict[str, Any]],
    ) -> Optional[Tuple[float, float, float]]:
        if data is None or not all(key in data for key in cls.DIMENSION_KEYS):
            return None

        values: List[float] = []
        for key in cls.DIMENSION_KEYS:
            value: Any = data[key]
            if isinstance(value, bool) or not isinstance(value, Real):
                return None
            numeric: float = float(value)
            if not isfinite(numeric) or numeric == 0.0:
                return None
            values.append(numeric)

        return values[0], values[1], values[2]

    @classmethod
    def _position(cls, context: CliContextPort) -> Dict[str, float]:
        value: Any = context.get_parameter_value(cls.POSITION_KEY)
        if not isinstance(value, dict):
            raise IfcCreationError("The geometry position is not defined.")

        position: Dict[str, float] = {}
        for axis in ("x", "y", "z"):
            coordinate: Any = value.get(axis)
            if isinstance(coordinate, bool) or not isinstance(coordinate, Real):
                raise IfcCreationError(
                    f"The position {axis} coordinate is not a real number."
                )
            numeric: float = float(coordinate)
            if not isfinite(numeric):
                raise IfcCreationError(
                    f"The position {axis} coordinate must be finite."
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
        """
        Return the schema the product is assembled in.

        The target model's own, read from it, so what this state writes
        merges into that model without a conversion. Without a target
        model there is nothing to agree with, and the default schema is
        what the primitive is written in.
        """
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
                f"Box geometry creation supports the "
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
