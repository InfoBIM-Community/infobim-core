from typing import Any, Dict, List, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.domain.model.view import DrawingView
from infobim.drawing.adapter.view_writer import DxfDrawingViewWriter
from infobim.drawing.adapter.view_context import DrawingViewContext
from infobim.drawing.adapter.transformation_payload import DrawingViewPayloadPath


class DrawingViewsExtractedCapability(TransformationCapability):
    """
    Write each Drawing View into a DXF of its own inside the project.

    The DXFs go to the project's drawing payload, in the directory of the
    drawing's content. A sheet where no view was found writes nothing.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_views_extracted"
        ),
        version="0.1.0",
        name="Drawing Views Extracted",
        description=(
            "Write each classified Drawing View of the sheet into a DXF of "
            "its own, named after its title, inside the project."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "view", "extraction"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.CONTAINER_PATH: {"type": "string", "required": True},
                DrawingViewContextKeys.DRAWING_PATH: {"type": "string", "required": True},
                DrawingViewContextKeys.DXF_DOCUMENTS: {"type": "object", "required": True},
                DrawingViewContextKeys.SHEET_ENTITIES: {"type": list, "required": True},
                DrawingViewContextKeys.VIEWS: {"type": list, "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.VIEWS: {"type": "array"},
                DrawingViewContextKeys.VIEWS_DIRECTORY: {"type": "string"},
            },
        },
        log_message={
            "info": {
                "en": "The Drawing Views of the sheet were extracted into DXF files.",
            },
            "debug_entry": {"en": "Extracting the Drawing Views of the sheet."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        views: List[DrawingView] = DrawingViewContext.views(context)
        directory: Optional[str] = None
        if views:
            path: Path = DrawingViewPayloadPath.directory_for(
                Path(RequiredParameter.of(context, DrawingViewContextKeys.CONTAINER_PATH))
                .expanduser()
                .resolve(),
                Path(RequiredParameter.of(context, DrawingViewContextKeys.DRAWING_PATH))
                .expanduser()
                .resolve(),
            )
            views = DxfDrawingViewWriter().write(
                DrawingViewContext.document(context),
                DrawingViewContext.entities(context),
                views,
                path,
            )
            directory = str(path)
        context.set_parameter_value(DrawingViewContextKeys.VIEWS, views)
        context.set_parameter_value(DrawingViewContextKeys.VIEWS_DIRECTORY, directory)
        return {
            DrawingViewContextKeys.VIEWS: views,
            DrawingViewContextKeys.VIEWS_DIRECTORY: directory,
        }
