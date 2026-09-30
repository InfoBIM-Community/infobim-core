from typing import Any, ClassVar, Dict

from ezdxf.document import Drawing
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim._2d.domain.port.viewer import DxfViewerSessionPort
from infobim._2d.adapter.dxf_viewer import DxfViewerDocuments, DxfViewerSessionFactory


class DxfViewerSessionOpenedCapability(DataLoaderCapability):
    """
    Open the 2D viewer window on the loaded drawings without blocking, and
    leave the session in the context for the interaction that follows on
    the same window.
    """

    SESSION_KEY: ClassVar[str] = "dxf_viewer_session"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._2d.plugin.capability.loader.dxf_viewer_session",
        version="1.0.0",
        name="DXF Viewer Session Opened",
        description=(
            "Open the InfoBIM 2D viewer window on the loaded DXF documents "
            "and keep its session in the context."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "dxf", "viewer", "session"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                DxfViewerDocuments.DOCUMENTS_KEY: {"type": "object", "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                SESSION_KEY: {"type": DxfViewerSessionPort},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        documents: Dict[str, Drawing] = DxfViewerDocuments.from_context(context)
        session: DxfViewerSessionPort = DxfViewerSessionFactory.open(documents)
        session.show()
        context.set_parameter_value(self.SESSION_KEY, session)
        return {self.SESSION_KEY: session}
