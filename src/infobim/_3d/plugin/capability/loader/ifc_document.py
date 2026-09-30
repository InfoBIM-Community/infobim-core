from typing import Any, ClassVar, Dict
from pathlib import Path

import ifcopenshell

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class IfcDocumentLoaderCapability(DataLoaderCapability):
    """Open the requested IFC file with IfcOpenShell and inject its model into the context."""

    PATH_KEY: ClassVar[str] = "file_open_path"
    MODEL_KEY: ClassVar[str] = "ifc_model"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._3d.plugin.capability.loader.ifc_document",
        version="1.0.0",
        name="IFC Document Loader",
        description=(
            "Open the requested IFC file with IfcOpenShell and inject the "
            "resulting model into the context."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "3d", "ifc", "loader", "read-only"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                PATH_KEY: {"type": "string", "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                MODEL_KEY: {"type": ifcopenshell.file, "required": True},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "IFC Document Loader"

    def description(self, lang: str = "en") -> str:
        return "Opens the requested IFC file and injects its model into the context."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ifc_path: Path = Path(
            RequiredParameter.of(context, self.PATH_KEY)
        ).expanduser().resolve()
        model: ifcopenshell.file = ifcopenshell.open(str(ifc_path))
        context.set_parameter_value(self.MODEL_KEY, model)
        return {self.MODEL_KEY: model}
