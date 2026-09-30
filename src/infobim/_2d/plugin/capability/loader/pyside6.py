from typing import Any, ClassVar, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.open_file import (
    OPEN_FILE_INPUT_SCHEMA,
    OPEN_FILE_OUTPUT_SCHEMA,
)
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport

from infobim._2d.adapter.dwg import DwgToDxfOpenFileConversion
from infobim._2d.plugin.machine.dxf_viewer.machine import DxfViewerStateTransitionHandler


class PySide6OpenFileCapability(DataLoaderCapability, OpenFileChainSupport):
    """
    Open-file capability for drawings shown with PySide6.

    It dispatches on the MIME type identified by the open-file flow and
    delegates to state machines on the same context: a DWG file is first
    converted into DXF by the DWG to DXF machine, and the DXF (the requested
    one, or the converted one) is loaded and shown by the DXF viewer machine.
    """

    DXF_MIME_TYPE: ClassVar[str] = "image/vnd.dxf"
    DWG_MIME_TYPE: ClassVar[str] = "image/vnd.dwg"
    HANDLER_NAME: ClassVar[str] = "pyside6"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._2d.plugin.capability.loader.pyside6",
        version="1.0.0",
        name="Open File with PySide6",
        description="Open a local DXF or DWG file in the InfoBIM 2D viewer (PySide6).",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "open_file", "chain"],
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
        mime_type: Any = context.get_parameter_value(self.MIME_KEY)
        return mime_type in (self.DXF_MIME_TYPE, self.DWG_MIME_TYPE)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        mime_type: Any = context.get_parameter_value(self.MIME_KEY)
        if mime_type == self.DWG_MIME_TYPE:
            DwgToDxfOpenFileConversion.convert(context)
        elif mime_type != self.DXF_MIME_TYPE:
            raise ValueError(
                f"MIME type {mime_type!r} is not supported by "
                f"{type(self).__name__}; it opens only '{self.DXF_MIME_TYPE}' "
                f"and '{self.DWG_MIME_TYPE}'."
            )

        DxfViewerStateTransitionHandler(context).execute()
        return {
            "handled": True,
            "handler": self.HANDLER_NAME,
            "message": "Opened the DXF file in the InfoBIM 2D viewer.",
            "error": None,
        }
