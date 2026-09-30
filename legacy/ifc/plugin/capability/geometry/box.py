from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.domain.port.geometry import GeometryProducerPort


class BoxGeometryCapability(Capability, GeometryProducerPort):
    """
    Produces a rectangular parallelepiped geometry from its three orthogonal dimensions.

    Producing geometry is not transforming a product: nothing here reads
    or changes an IFC entity, and nothing here decides which IFC class the
    geometry will represent. The result is a ``GeometryDefinition`` — a
    serializable value, not a reader entity — which is what makes
    ``GEOMETRY_DEFINED`` a state of the definition rather than of the model.

    STUB.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.geometry.box",
        version="0.1.0",
        name="Box Geometry",
        description="Produce a rectangular parallelepiped geometry definition.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometry", "box"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "width": {
                    "type": "string",
                    "required": True,
                    "description": "Dimension of the solid along its own X axis.",
                },
                "depth": {
                    "type": "string",
                    "required": True,
                    "description": "Dimension of the solid along its own Y axis.",
                },
                "height": {
                    "type": "string",
                    "required": True,
                    "description": "Dimension of the solid along its own Z axis.",
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

    WIDTH_KEY: ClassVar[str] = "width"
    DEPTH_KEY: ClassVar[str] = "depth"
    HEIGHT_KEY: ClassVar[str] = "height"


    def label(self, lang: str = "en") -> str:
        return "Box Geometry"

    def description(self, lang: str = "en") -> str:
        return "Produces a rectangular parallelepiped geometry definition."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raise NotImplementedError(
            "Producing a rectangular parallelepiped geometry definition is not implemented yet."
        )

    def geometry(self, context: CliContextPort) -> GeometryDefinition:
        raise NotImplementedError(
            "Producing the geometry definition is not implemented yet."
        )
