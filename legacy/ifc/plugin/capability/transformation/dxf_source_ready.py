from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.plugin.machine.dxf_import.state import (
    IfcImportContextKeys,
    IfcImportProcessState,
)


class DxfSourceReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "dxf_source_ready"
        ),
        version="0.1.0",
        name="DXF Source Ready",
        description="Resolve and validate the DXF source selected for IFC import.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "dxf", "import"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                IfcImportContextKeys.IMPORT_PATH_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                IfcImportContextKeys.DXF_SOURCE_KEY: {"type": "string"},
            },
            "required": [IfcImportContextKeys.DXF_SOURCE_KEY],
        },
    )

    def label(self, lang: str = "en") -> str:
        return IfcImportProcessState.DXF_SOURCE_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return "Resolve and validate the DXF source selected for IFC import."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw: Any = context.get_parameter_value(
            IfcImportContextKeys.IMPORT_PATH_KEY
        )
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("DXF import source path is missing.")

        source = Path(raw).expanduser().resolve()
        if source.suffix.lower() != ".dxf":
            raise ValueError(f"Not a DXF source: {source}")
        if not source.is_file():
            raise ValueError(f"DXF source file not found: {source}")

        context.set_parameter_value(
            IfcImportContextKeys.DXF_SOURCE_KEY,
            str(source),
        )
        return {
            "resulting_state": IfcImportProcessState.DXF_SOURCE_READY,
            IfcImportContextKeys.DXF_SOURCE_KEY: str(source),
        }
