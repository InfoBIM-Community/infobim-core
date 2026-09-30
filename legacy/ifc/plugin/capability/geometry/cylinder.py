from math import isfinite
from numbers import Real
from typing import Any, ClassVar, Dict, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import GeometryDefinitionInvalidError
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.domain.port.geometry import GeometryProducerPort


class CylinderGeometryCapability(Capability, GeometryProducerPort):
    """Produce a cylinder definition from radius, height and axis direction."""

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.geometry.cylinder",
        version="0.1.0",
        name="Cylinder Geometry",
        description="Produce a cylindrical geometry definition.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometry", "cylinder"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "radius": {
                    "required": True,
                    "description": "Positive radius of the circular profile.",
                },
                "height": {
                    "required": True,
                    "description": "Positive height along the cylinder axis.",
                },
                "direction_x": {
                    "required": True,
                    "description": "X component of the cylinder axis direction.",
                },
                "direction_y": {
                    "required": True,
                    "description": "Y component of the cylinder axis direction.",
                },
                "direction_z": {
                    "required": True,
                    "description": "Z component of the cylinder axis direction.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "geometry": {"type": "object"},
            },
        },
    )

    RADIUS_KEY: ClassVar[str] = "radius"
    HEIGHT_KEY: ClassVar[str] = "height"
    DIRECTION_KEYS: ClassVar[Tuple[str, str, str]] = (
        "direction_x",
        "direction_y",
        "direction_z",
    )

    def label(self, lang: str = "en") -> str:
        return "Cylinder Geometry"

    def description(self, lang: str = "en") -> str:
        return "Produce a cylindrical geometry definition."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        geometry: GeometryDefinition = self.geometry(context)
        context.set_parameter_value(self.GEOMETRY_KEY, geometry)
        return {self.GEOMETRY_KEY: geometry.to_dict()}

    def geometry(self, context: CliContextPort) -> GeometryDefinition:
        radius: float = self._positive(context, self.RADIUS_KEY)
        height: float = self._positive(context, self.HEIGHT_KEY)
        direction: Tuple[float, float, float] = tuple(
            self._finite(context, key) for key in self.DIRECTION_KEYS
        )
        if direction == (0.0, 0.0, 0.0):
            raise GeometryDefinitionInvalidError(
                "The cylinder direction vector cannot be the zero vector."
            )

        return GeometryDefinition(
            kind=GeometryDefinition.CYLINDER_KIND,
            parameters=(
                (self.RADIUS_KEY, radius),
                (self.HEIGHT_KEY, height),
                (self.DIRECTION_KEYS[0], direction[0]),
                (self.DIRECTION_KEYS[1], direction[1]),
                (self.DIRECTION_KEYS[2], direction[2]),
            ),
        )

    @staticmethod
    def _finite(context: CliContextPort, key: str) -> float:
        if not context.has_parameter(key):
            raise GeometryDefinitionInvalidError(
                f"Cylinder geometry requires '{key}'."
            )
        value: Any = context.get_parameter_value(key)
        if isinstance(value, bool) or not isinstance(value, Real):
            raise GeometryDefinitionInvalidError(
                f"Cylinder geometry parameter '{key}' must be a real number."
            )
        numeric: float = float(value)
        if not isfinite(numeric):
            raise GeometryDefinitionInvalidError(
                f"Cylinder geometry parameter '{key}' must be finite."
            )
        return numeric

    @classmethod
    def _positive(cls, context: CliContextPort, key: str) -> float:
        numeric: float = cls._finite(context, key)
        if numeric <= 0.0:
            raise GeometryDefinitionInvalidError(
                f"Cylinder geometry parameter '{key}' must be positive."
            )
        return numeric
