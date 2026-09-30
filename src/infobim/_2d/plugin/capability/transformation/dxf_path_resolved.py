from typing import Any, ClassVar, Dict, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.open_file_metadata import OpenFileMetadataEvent
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport

from infobim._2d.adapter.dwg import DwgToDxfOpenFileConversion


class DxfPathResolvedCapability(TransformationCapability):
    """
    Make the open-file path point at a DXF drawing.

    The MIME type comes from the file metadata event extracted for the
    current open-file path. A DXF path is kept as is; a DWG file is
    converted into DXF and the open-file path is replaced by the converted
    DXF. Any other MIME type is rejected.
    """

    DXF_MIME_TYPE: ClassVar[str] = "image/vnd.dxf"
    DWG_MIME_TYPE: ClassVar[str] = "image/vnd.dwg"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._2d.plugin.capability.transformation.dxf_path_resolved",
        version="1.0.0",
        name="DXF Path Resolved",
        description=(
            "Keep a DXF open-file path, or convert a DWG file into DXF and "
            "point the open-file path at the converted drawing."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "dxf", "dwg", "transformation"],
        supported_languages=["en"],
        input_schema={
            "properties": {
                OpenFileChainSupport.PATH_KEY: {"type": "string", "required": True},
            },
        },
        output_schema={
            "properties": {
                OpenFileChainSupport.PATH_KEY: {"type": "string"},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        file_path: str = RequiredParameter.of(context, OpenFileChainSupport.PATH_KEY)
        mime_type: Optional[str] = OpenFileMetadataEvent.mime_for(
            StorageBootstrap.get_init_root_path(context=context),
            Path(file_path),
        )
        if mime_type == self.DWG_MIME_TYPE:
            file_path = DwgToDxfOpenFileConversion.convert(context)
        elif mime_type != self.DXF_MIME_TYPE:
            raise ValueError(
                f"MIME type {mime_type!r} of {file_path!r} is not supported; "
                f"only '{self.DXF_MIME_TYPE}' and '{self.DWG_MIME_TYPE}' "
                "drawings can be loaded."
            )

        return {OpenFileChainSupport.PATH_KEY: file_path}
