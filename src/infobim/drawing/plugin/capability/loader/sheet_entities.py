from typing import Any, Dict, List

from ezdxf.document import Drawing

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.sheet import DxfSheetIndex
from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.domain.model.sheet import SheetEntity
from infobim.drawing.adapter.view_context import DrawingViewContext


class DrawingSheetEntitiesLoaderCapability(DataLoaderCapability):
    """Index the model space of the loaded sheet, each entity with its extents."""

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.drawing.plugin.capability.loader.drawing_sheet_entities",
        version="0.1.0",
        name="Drawing Sheet Entities",
        description=(
            "Index the model-space entities of the loaded DXF sheet with their "
            "extents, texts, block names and outline shapes."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "view", "loader", "read-only"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.DXF_DOCUMENTS: {
                    "type": "object",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.SHEET_ENTITIES: {"type": "array"},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document: Drawing = DrawingViewContext.document(context)
        entities: List[SheetEntity] = DxfSheetIndex.of(document)
        context.set_parameter_value(DrawingViewContextKeys.SHEET_ENTITIES, entities)
        return {DrawingViewContextKeys.SHEET_ENTITIES: entities}
