from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.domain.model.view import DrawingView
from infobim.drawing.adapter.view_context import DrawingViewContext
from infobim.drawing.adapter.view_classifier import (
    DrawingViewClassifier,
    DrawingViewSettlement,
)
from infobim.drawing.domain.model.view_candidates import DrawingViewCandidates


class DrawingViewsClassifiedCapability(TransformationCapability):
    """
    Settle the delimited candidates into classified Drawing Views.

    Classification comes after segmentation and only reads the evidence the
    candidates gathered. A candidate that no region delimited has no part of
    the sheet to show and does not become a view.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_views_classified"
        ),
        version="0.1.0",
        name="Drawing Views Classified",
        description=(
            "Classify each delimited Drawing View candidate as a plan, "
            "section, elevation or detail view, and settle it into a Drawing "
            "View."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "view", "classification"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.CANDIDATES: {
                    "type": DrawingViewCandidates,
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.VIEWS: {"type": "array"},
            },
        },
        log_message={
            "info": {"en": "The Drawing Views of the sheet were classified."},
            "debug_entry": {"en": "Classifying the Drawing Views of the sheet."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        candidates: DrawingViewCandidates = DrawingViewContext.candidates(context)
        views: List[DrawingView] = DrawingViewSettlement(DrawingViewClassifier()).views(
            candidates.located()
        )
        context.set_parameter_value(DrawingViewContextKeys.VIEWS, views)
        return {DrawingViewContextKeys.VIEWS: views}
