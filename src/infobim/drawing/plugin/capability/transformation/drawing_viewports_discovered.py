from typing import Any, Dict, Optional, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.domain.model.view import DrawingBoundary, DrawingViewEvidence
from infobim.drawing.adapter.view_context import DrawingViewContext
from infobim.drawing.adapter.view_viewport import DxfViewportRegions
from infobim.drawing.domain.model.view_candidates import DrawingViewCandidates


class DrawingViewportsDiscoveredCapability(TransformationCapability):
    """
    Open the candidates of a sheet with the regions its viewports show.

    A viewport is the most explicit limit a view can have: the CAD structure
    itself says which part of the model it shows, and at which scale. This
    state starts the one candidate collection every later state refines; a
    sheet without viewports starts it empty.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_viewports_discovered"
        ),
        version="0.1.0",
        name="Drawing Viewports Discovered",
        description=(
            "Open the Drawing View candidates of the loaded sheet with the "
            "model-space regions its paper-space viewports show."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "view", "viewport"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                DrawingViewContextKeys.DXF_DOCUMENTS: {"type": "object", "required": True},
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
                "en": "The viewports of the sheet opened its Drawing View candidates.",
            },
            "debug_entry": {"en": "Discovering the viewports of the sheet."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        candidates: DrawingViewCandidates = DrawingViewCandidates()
        region: Tuple[DrawingBoundary, Optional[str]]
        for region in DxfViewportRegions.of(DrawingViewContext.document(context)):
            candidates.add_region(region[0], DrawingViewEvidence.VIEWPORT, region[1])
        context.set_parameter_value(DrawingViewContextKeys.CANDIDATES, candidates)
        return {DrawingViewContextKeys.CANDIDATES: candidates}
