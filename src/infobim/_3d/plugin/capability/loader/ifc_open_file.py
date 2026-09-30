from typing import Any, ClassVar, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.open_file import (
    OPEN_FILE_INPUT_SCHEMA,
    OPEN_FILE_OUTPUT_SCHEMA,
)
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport

from infobim._3d.adapter.taxonomy import IfcMimeTaxonomy
from infobim._3d.plugin.machine.ifc_viewer.machine import IfcViewerStateTransitionHandler


class IfcOpenFileCapability(DataLoaderCapability, OpenFileChainSupport):
    """
    Open-file capability for IFC models shown in the InfoBIM 3D viewer.

    It dispatches on the MIME type identified by the open-file flow and
    delegates to the IFC viewer state machine, which loads the model,
    triangulates it into Qt Quick 3D geometries and opens the viewer on the
    same context.
    """

    IFC_MIME_TYPE: ClassVar[str] = IfcMimeTaxonomy.PART21
    HANDLER_NAME: ClassVar[str] = "ifc_quick3d"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._3d.plugin.capability.loader.ifc_open_file",
        version="1.0.0",
        name="Open IFC File in 3D",
        description="Open a local IFC file in the InfoBIM 3D viewer (Qt Quick 3D).",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "3d", "ifc", "open_file", "chain"],
        supported_languages=["en"],
        input_schema={
            "properties": {
                **OPEN_FILE_INPUT_SCHEMA["properties"],
                OpenFileChainSupport.MIME_KEY: {"type": "string", "required": True},
            },
        },
        output_schema=OPEN_FILE_OUTPUT_SCHEMA,
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def can_handle(
        self,
        context: CliContextPort,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return context.get_parameter_value(self.MIME_KEY) in IfcMimeTaxonomy.SUPPORTED

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        mime_type: Any = context.get_parameter_value(self.MIME_KEY)
        if mime_type not in IfcMimeTaxonomy.SUPPORTED:
            raise ValueError(
                f"MIME type {mime_type!r} is not supported by "
                f"{type(self).__name__}; supported types: {IfcMimeTaxonomy.SUPPORTED}."
            )

        IfcViewerStateTransitionHandler(context).execute()
        return {
            "handled": True,
            "handler": self.HANDLER_NAME,
            "message": "Opened the IFC file in the InfoBIM 3D viewer.",
            "error": None,
        }
