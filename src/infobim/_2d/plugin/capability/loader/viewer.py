from typing import Any, ClassVar, Dict

from ezdxf.document import Drawing
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim._2d.domain.port.viewer import DxfViewerSessionPort
from infobim._2d.adapter.dxf_viewer import DxfViewerDocuments, DxfViewerSessionFactory


class DxfViewerCapability(DataLoaderCapability):
    """Open one DXF viewer and switch between available document states."""

    DOCUMENTS_KEY: ClassVar[str] = DxfViewerDocuments.DOCUMENTS_KEY
    SELECTED_STATE_KEY: ClassVar[str] = "dxf_viewer_state"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.drawing.plugin.capability.loader.dxf_viewer",
        version="1.0.0",
        name="DXF Viewer",
        description=(
            "Open a single interactive DXF viewer and switch between original, "
            "annotated, and suggested drawing states."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "2d", "viewer", "read-only"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                DOCUMENTS_KEY: {"type": "object", "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                SELECTED_STATE_KEY: {"type": "string"},
                "available_states": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": [SELECTED_STATE_KEY, "available_states"],
        },
    )

    def label(self, lang: str = "en") -> str:
        return "DXF Viewer"

    def description(self, lang: str = "en") -> str:
        return "Opens one DXF viewer with tabs for the available drawing states."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        documents: Dict[str, Drawing] = DxfViewerDocuments.from_context(context)
        session: DxfViewerSessionPort = DxfViewerSessionFactory.open(documents)
        try:
            selected_state: str = session.run()
        finally:
            session.close()
        context.set_parameter_value(self.SELECTED_STATE_KEY, selected_state)
        return {
            self.SELECTED_STATE_KEY: selected_state,
            "available_states": list(documents),
        }
