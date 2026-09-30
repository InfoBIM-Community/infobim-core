from typing import Any, Dict, List, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.domain.model.view import DrawingViewReference
from infobim.drawing.adapter.view_context import DrawingViewContext
from infobim.drawing.adapter.view_reference import DrawingViewReferenceReader
from infobim.drawing.domain.model.view_candidates import DrawingViewCandidates


class DrawingViewReferencesDetectedCapability(TransformationCapability):
    """
    Attach the graphic references of the sheet to the candidates.

    A label such as ``A-A`` names the view it is written under and opens a
    candidate when no other evidence did; a mark drawn inside a view is kept
    as evidence of that view, and waits for a region when none holds it yet.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_references_detected"
        ),
        version="0.1.0",
        name="Drawing View References Detected",
        description=(
            "Detect section labels, detail bubbles and view marks on the "
            "sheet and attach them to the candidates as evidence."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "view", "reference", "section", "detail"],
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
                "en": "The references of the sheet were attached to its Drawing View candidates.",
            },
            "debug_entry": {"en": "Detecting the Drawing View references of the sheet."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        candidates: DrawingViewCandidates = DrawingViewContext.candidates(context)
        found: List[Tuple[DrawingViewReference, float]] = (
            DrawingViewReferenceReader.references(DrawingViewContext.entities(context))
        )
        reference: DrawingViewReference
        height: float
        for reference, height in found:
            candidates.add_reference(reference, height)
        context.set_parameter_value(DrawingViewContextKeys.CANDIDATES, candidates)
        return {DrawingViewContextKeys.CANDIDATES: candidates}
