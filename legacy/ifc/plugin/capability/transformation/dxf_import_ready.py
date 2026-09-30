from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.plugin.machine.dxf_import.state import (
    IfcImportContextKeys,
    IfcImportProcessState,
)


class DxfImportReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "import_ready"
        ),
        version="0.1.0",
        name="DXF Import Ready",
        description=(
            "Confirm that the DXF source, representation kind, and geometry "
            "are ready for future IFC-writing states."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "dxf", "import"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                IfcImportContextKeys.DXF_SOURCE_KEY: {
                    "type": "string",
                    "required": True,
                },
                IfcImportContextKeys.REPRESENTATION_KIND_KEY: {
                    "type": "string",
                    "required": True,
                },
                IfcImportContextKeys.DXF_GEOMETRY_KEY: {
                    "type": "object",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                IfcImportContextKeys.IMPORT_READY_KEY: {"type": "boolean"},
            },
            "required": [IfcImportContextKeys.IMPORT_READY_KEY],
        },
    )

    def label(self, lang: str = "en") -> str:
        return IfcImportProcessState.IMPORT_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return (
            "Confirm that the DXF source, representation kind, and geometry "
            "are ready for future IFC-writing states."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        source = context.get_parameter_value(IfcImportContextKeys.DXF_SOURCE_KEY)
        kind = context.get_parameter_value(
            IfcImportContextKeys.REPRESENTATION_KIND_KEY
        )
        geometry = context.get_parameter_value(
            IfcImportContextKeys.DXF_GEOMETRY_KEY
        )
        if not isinstance(source, str) or not source.strip():
            raise ValueError("DXF source is not ready.")
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("IFC representation kind is not ready.")
        if not isinstance(geometry, dict):
            raise ValueError("DXF geometry has not been read.")

        context.set_parameter_value(
            IfcImportContextKeys.IMPORT_READY_KEY,
            True,
        )
        return {
            "resulting_state": IfcImportProcessState.IMPORT_READY,
            IfcImportContextKeys.IMPORT_READY_KEY: True,
        }
