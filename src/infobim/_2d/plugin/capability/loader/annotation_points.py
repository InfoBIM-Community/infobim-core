from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim._2d.domain.port.viewer import DxfViewerSessionPort


class DxfAnnotationPointsCapability(DataLoaderCapability):
    """
    Capture points on the open 2D viewer session, for an annotation.

    Each left click adds a point, Backspace or Delete removes the last one
    and a left double click adds a last point and finishes the capture. The
    points, in click order, are left in the context. The window stays open:
    whoever asks for what comes next on it closes it. It is closed here only
    when the capture fails.
    """

    SESSION_KEY: ClassVar[str] = "dxf_viewer_session"
    POINTS_KEY: ClassVar[str] = "captured_points"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._2d.plugin.capability.loader.dxf_annotation_points",
        version="1.0.0",
        name="DXF Annotation Points Captured",
        description=(
            "Capture drawing points on the open InfoBIM 2D viewer session, "
            "in click order, and keep the window open for what follows."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "dxf", "viewer", "points"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                SESSION_KEY: {"type": DxfViewerSessionPort, "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                POINTS_KEY: {"type": "array"},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        session: DxfViewerSessionPort = context.get_parameter_value(self.SESSION_KEY)
        try:
            points: List[Dict[str, float]] = session.capture_points()
        except BaseException:
            session.close()
            raise
        context.set_parameter_value(self.POINTS_KEY, points)
        return {self.POINTS_KEY: points}
