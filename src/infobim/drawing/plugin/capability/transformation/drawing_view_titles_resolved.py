from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.domain.model.view import DrawingViewTitle
from infobim.drawing.adapter.view_title import DrawingViewTitleReader
from infobim.drawing.adapter.view_context import DrawingViewContext
from infobim.drawing.domain.model.view_candidates import DrawingViewCandidates


class DrawingViewTitlesResolvedCapability(TransformationCapability):
    """
    Give the candidates the titles written on the sheet, with their scale.

    A title names the view it is written in or next to; a title that no
    located candidate reaches yet stays as an unlocated candidate, placed by
    the title itself, until a later state finds the region it names.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_titles_resolved"
        ),
        version="0.1.0",
        name="Drawing View Titles Resolved",
        description=(
            "Resolve the texts that title the Drawing Views of the sheet, "
            "with their scale and position, and give each to the candidate it"
            " names."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "view", "title", "scale"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.SHEET_ENTITIES: {"type": list, "required": True},
                DrawingViewContextKeys.CANDIDATES: {
                    "type": DrawingViewCandidates,
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.CANDIDATES: {"type": "object"},
            },
        },
        log_message={
            "info": {
                "en": "The titles of the sheet were given to its Drawing View candidates.",
            },
            "debug_entry": {"en": "Resolving the Drawing View titles of the sheet."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        candidates: DrawingViewCandidates = DrawingViewContext.candidates(context)
        title: DrawingViewTitle
        for title in DrawingViewTitleReader.titles(DrawingViewContext.entities(context)):
            candidates.add_title(title)
        context.set_parameter_value(DrawingViewContextKeys.CANDIDATES, candidates)
        return {DrawingViewContextKeys.CANDIDATES: candidates}
