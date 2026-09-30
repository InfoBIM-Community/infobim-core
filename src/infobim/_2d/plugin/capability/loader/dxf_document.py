from typing import Any, ClassVar, Dict
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class DxfDocumentLoaderCapability(DataLoaderCapability):
    """Read the requested DXF file and inject its document into the context."""

    PATH_KEY: ClassVar[str] = "file_open_path"
    DOCUMENTS_KEY: ClassVar[str] = "dxf_documents"
    ORIGINAL_KEY: ClassVar[str] = "dxf_original"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._2d.plugin.capability.loader.dxf_document",
        version="1.0.0",
        name="DXF Document Loader",
        description=(
            "Read the requested DXF file with ezdxf and inject the resulting "
            "document into the context's DXF documents as the original drawing."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "dxf", "loader", "read-only"],
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
                DOCUMENTS_KEY: {"type": "object", "required": True},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "DXF Document Loader"

    def description(self, lang: str = "en") -> str:
        return "Reads the requested DXF file and injects it into the context."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        dxf_path: Path = Path(
            RequiredParameter.of(context, self.PATH_KEY)
        ).expanduser().resolve()
        documents: Dict[str, Drawing] = {
            self.ORIGINAL_KEY: ezdxf.readfile(str(dxf_path)),
        }
        context.set_parameter_value(self.DOCUMENTS_KEY, documents)
        return {self.DOCUMENTS_KEY: documents}
