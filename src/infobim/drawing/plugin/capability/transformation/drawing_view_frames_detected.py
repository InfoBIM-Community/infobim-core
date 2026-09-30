from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.domain.model.view import DrawingBoundary, DrawingViewEvidence
from infobim.drawing.adapter.view_frame import DrawingViewFrameFinder
from infobim.drawing.domain.model.sheet import SheetEntity
from infobim.drawing.adapter.view_context import DrawingViewContext
from infobim.drawing.domain.model.view_candidates import DrawingViewCandidates


class DrawingViewFramesDetectedCapability(TransformationCapability):
    """
    Delimit the candidates with the frames drawn around views.

    A frame refines the candidate it coincides with, delimits the titled
    candidates it holds, and opens a candidate of its own otherwise.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_frames_detected"
        ),
        version="0.1.0",
        name="Drawing View Frames Detected",
        description=(
            "Detect the drawn frames that delimit Drawing Views on the sheet "
            "and refine the candidates with them."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "view", "frame"],
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
                "en": "The frames of the sheet refined its Drawing View candidates.",
            },
            "debug_entry": {"en": "Detecting the Drawing View frames of the sheet."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        candidates: DrawingViewCandidates = DrawingViewContext.candidates(context)
        entities: List[SheetEntity] = DrawingViewContext.entities(context)
        frame: DrawingBoundary
        for frame in DrawingViewFrameFinder.frames(entities, candidates.titles()):
            candidates.add_region(frame, DrawingViewEvidence.FRAME)
        context.set_parameter_value(DrawingViewContextKeys.CANDIDATES, candidates)
        return {DrawingViewContextKeys.CANDIDATES: candidates}
