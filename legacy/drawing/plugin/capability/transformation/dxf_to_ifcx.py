from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.dxf_to_ifcx import DxfToIfcxConverter


class DxfToIfcxCapability(TransactionCapability):
    """
    Converts a DXF file into an IFCX payload cached under the container.

    The conversion itself, including the entity-walking rules and the
    content-addressed cache path, lives in DxfToIfcxConverter; this
    capability only adapts that transformation to the capability contract.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    DXF_PATH_KEY: ClassVar[str] = "dxf_path"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.drawing.plugin.capability.transformation.dxf_to_ifcx",
        version="1.0.0",
        name="DXF to IFCX",
        description=(
            "Convert a DXF file into an IFCX payload cached under the "
            "container's reserved InfoBIM dataset."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "ifcx", "transformation"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                },
                "dxf_path": {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "ifcx_path": {"type": "string"},
            },
            "required": ["source", "ifcx_path"],
        },
    )

    def label(self, lang: str = "en") -> str:
        return "DXF to IFCX"

    def description(self, lang: str = "en") -> str:
        return (
            "Converts a DXF file into an IFCX payload cached under the "
            "container."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Convert the DXF named by the context into a cached IFCX payload.
        """
        container_value: Any = context.get_parameter_value(
            self.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise ValueError(
                "The container path is missing from the command context."
            )

        dxf_value: Any = context.get_parameter_value(self.DXF_PATH_KEY)
        if not isinstance(dxf_value, str) or not dxf_value.strip():
            raise ValueError(
                "The DXF source path is missing from the command context."
            )

        container_path: Path = Path(container_value).expanduser().resolve()
        source_path: Path = Path(dxf_value).expanduser().resolve()

        destination: Path = DxfToIfcxConverter().convert(
            container_path, source_path
        )

        return {
            "source": str(source_path),
            "ifcx_path": str(destination),
        }
