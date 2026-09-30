from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from infobim.drawing.adapter.dwg_to_dxf import DwgToDxfConverter


class DwgToDxfCapability(TransactionCapability):
    """
    Converts a DWG file into a DXF payload cached under the container.

    The conversion itself, including the ODA File Converter invocation and
    the content-addressed cache path, lives in DwgToDxfConverter; this
    capability only adapts that transformation to the capability contract.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    DWG_PATH_KEY: ClassVar[str] = "dwg_path"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.drawing.plugin.capability.transformation.dwg_to_dxf",
        version="1.0.0",
        name="DWG to DXF",
        description=(
            "Convert a DWG file into a DXF payload cached under the "
            "container's reserved InfoBIM dataset."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dwg", "dxf", "transformation"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                },
                "dwg_path": {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "dxf_path": {"type": "string"},
            },
            "required": ["source", "dxf_path"],
        },
    )

    def label(self, lang: str = "en") -> str:
        return "DWG to DXF"

    def description(self, lang: str = "en") -> str:
        return (
            "Converts a DWG file into a DXF payload cached under the "
            "container."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Convert the DWG named by the context into a cached DXF payload.
        """
        container_value: Any = context.get_parameter_value(
            self.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise ValueError(
                "The container path is missing from the command context."
            )

        dwg_value: Any = context.get_parameter_value(self.DWG_PATH_KEY)
        if not isinstance(dwg_value, str) or not dwg_value.strip():
            raise ValueError(
                "The DWG source path is missing from the command context."
            )

        container_path: Path = Path(container_value).expanduser().resolve()
        source_path: Path = Path(dwg_value).expanduser().resolve()

        destination: Path = DwgToDxfConverter().convert(
            container_path, source_path
        )

        return {
            "source": str(source_path),
            "dxf_path": str(destination),
        }
