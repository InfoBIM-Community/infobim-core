from typing import Any, ClassVar, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import GeometryDefinitionInvalidError
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class GeometryDefinedCapability(TransactionCapability):
    """Carry the primitive geometry definition produced for this run."""

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometry_defined"
        ),
        version="0.1.0",
        name="Geometry Defined",
        description="Carry the geometry definition produced for this run.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "geometry_defined"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "geometry": {
                    "type": "object",
                    "required": True,
                    "description": (
                        "The GeometryDefinition a geometry command produced "
                        "for this run."
                    ),
                    "uri": "org.infobim.ifc.geometry",
                },
            },
        },
        log_message={
            "info": {"en": "The primitive geometry is completely defined."},
            "debug_entry": {
                "en": "Reading the primitive geometry definition of this run."
            },
        },
    )

    GEOMETRY_KEY: ClassVar[str] = "geometry"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"

    def label(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.GEOMETRY_DEFINED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.GEOMETRY_DEFINED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        geometry: Optional[GeometryDefinition] = self._read_definition(context)
        if geometry is None:
            raise GeometryDefinitionInvalidError(
                "No valid geometry definition was produced for this run."
            )

        serialized: Dict[str, Any] = geometry.to_dict()
        context.set_parameter_value(self.GEOMETRY_KEY, serialized)

        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductCreateProcessState.GEOMETRY_DEFINED
            ),
            self.GEOMETRY_KEY: serialized,
        }

    @classmethod
    def _read_definition(
        cls,
        context: CliContextPort,
    ) -> Optional[GeometryDefinition]:
        if not context.has_parameter(cls.GEOMETRY_KEY):
            return None

        value: Any = context.get_parameter_value(cls.GEOMETRY_KEY)
        if isinstance(value, GeometryDefinition):
            return value
        if isinstance(value, dict):
            return GeometryDefinition.from_dict(value)
        return None
