from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.plugin.machine.dxf_import.state import (
    IfcImportContextKeys,
    IfcImportProcessState,
)


class RepresentationKindDefinedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "representation_kind_defined"
        ),
        version="0.1.0",
        name="Representation Kind Defined",
        description="Define the IFC representation kind requested for the DXF import.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "representation", "dxf", "import"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                IfcImportContextKeys.KIND_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                IfcImportContextKeys.REPRESENTATION_KIND_KEY: {
                    "type": "string"
                },
            },
            "required": [IfcImportContextKeys.REPRESENTATION_KIND_KEY],
        },
    )

    def label(self, lang: str = "en") -> str:
        return IfcImportProcessState.REPRESENTATION_KIND_DEFINED.label(lang)

    def description(self, lang: str = "en") -> str:
        return "Define the IFC representation kind requested for the DXF import."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw: Any = context.get_parameter_value(IfcImportContextKeys.KIND_KEY)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("IFC representation kind is missing.")

        kind = raw.strip()
        context.set_parameter_value(
            IfcImportContextKeys.REPRESENTATION_KIND_KEY,
            kind,
        )
        return {
            "resulting_state": IfcImportProcessState.REPRESENTATION_KIND_DEFINED,
            IfcImportContextKeys.REPRESENTATION_KIND_KEY: kind,
        }
