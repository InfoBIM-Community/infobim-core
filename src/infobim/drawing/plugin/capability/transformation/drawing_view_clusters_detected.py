from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.adapter.taxonomy import DrawingViewVocabulary
from infobim.drawing.domain.model.view import DrawingBoundary, DrawingViewCandidate
from infobim.drawing.adapter.view_cluster import (
    DrawingSpatialCluster,
    DrawingSpatialClusters,
)
from infobim.drawing.adapter.view_context import DrawingViewContext
from infobim.drawing.domain.model.view_candidates import DrawingViewCandidates


class DrawingViewClustersDetectedCapability(TransformationCapability):
    """
    Delimit, by spatial clustering, what the explicit evidence did not.

    Only the entities outside the regions already delimited are clustered.
    A cluster with drawing in it delimits the unlocated candidates it holds,
    or becomes a candidate of its own; a cluster of text alone is an
    annotation, and the sheet's title block is not a view. Titles still
    unlocated then join the nearest clustered view within reach.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.drawing.plugin.capability.transformation.target."
            "drawing_view_clusters_detected"
        ),
        version="0.1.0",
        name="Drawing View Clusters Detected",
        description=(
            "Group the entities no view delimits yet into spatial clusters "
            "and delimit the remaining candidates with them."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "dxf", "view", "cluster"],
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
                "en": "Spatial clusters delimited the remaining Drawing View candidates.",
            },
            "debug_entry": {"en": "Clustering the undelimited entities of the sheet."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        candidates: DrawingViewCandidates = DrawingViewContext.candidates(context)
        delimited: List[DrawingBoundary] = [
            self._boundary_of(candidate) for candidate in candidates.located()
        ]
        clusters: List[DrawingSpatialCluster] = DrawingSpatialClusters.of(
            DrawingViewContext.entities(context), delimited
        )
        cluster: DrawingSpatialCluster
        for cluster in clusters:
            if cluster.has_geometry and not DrawingViewVocabulary.is_title_block(
                list(cluster.texts)
            ):
                candidates.add_cluster(cluster.boundary)
        candidates.adopt_stray_unlocated()
        context.set_parameter_value(DrawingViewContextKeys.CANDIDATES, candidates)
        return {DrawingViewContextKeys.CANDIDATES: candidates}

    @staticmethod
    def _boundary_of(candidate: DrawingViewCandidate) -> DrawingBoundary:
        if candidate.boundary is None:
            raise ValueError("A located candidate carries no boundary.")
        return candidate.boundary
