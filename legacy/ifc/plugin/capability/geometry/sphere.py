from math import isfinite
from numbers import Real
from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import GeometryDefinitionInvalidError
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.domain.port.geometry import GeometryProducerPort


class SphereGeometryCapability(Capability, GeometryProducerPort):
    """Produce a sphere definition from a positive radius."""

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.geometry.sphere",
        version="0.1.0",
        name="Sphere Geometry",
        description="Produce a spherical geometry definition.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometry", "sphere"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "radius": {
                    "required": True,
                    "description": "Positive radius of the sphere.",
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

    def label(self, lang: str = "en") -> str:
        return "Sphere Geometry"

    def description(self, lang: str = "en") -> str:
        return "Produce a spherical geometry definition."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        geometry: GeometryDefinition = self.geometry(context)
        context.set_parameter_value(self.GEOMETRY_KEY, geometry)
        return {self.GEOMETRY_KEY: geometry.to_dict()}

    def geometry(self, context: CliContextPort) -> GeometryDefinition:
        radius: float = self._positive(context, self.RADIUS_KEY)
        return GeometryDefinition(
            kind=GeometryDefinition.SPHERE_KIND,
            parameters=((self.RADIUS_KEY, radius),),
        )

    @staticmethod
    def _positive(context: CliContextPort, key: str) -> float:
        if not context.has_parameter(key):
            raise GeometryDefinitionInvalidError(
                f"Sphere geometry requires '{key}'."
            )
        value: Any = context.get_parameter_value(key)
        if isinstance(value, bool) or not isinstance(value, Real):
            raise GeometryDefinitionInvalidError(
                f"Sphere geometry parameter '{key}' must be a real number."
            )
        numeric: float = float(value)
        if not isfinite(numeric) or numeric <= 0.0:
            raise GeometryDefinitionInvalidError(
                f"Sphere geometry parameter '{key}' must be positive and finite."
            )
        return numeric
