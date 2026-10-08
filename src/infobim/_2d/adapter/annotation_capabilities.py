from typing import ClassVar, Dict, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim._2d.plugin.capability.loader.annotation_details import (
    DxfAnnotationDetailsCapability,
)
from infobim._2d.plugin.capability.loader.annotation_points import (
    DxfAnnotationPointsCapability,
)
from infobim._2d.plugin.capability.loader.dxf_document import (
    DxfDocumentLoaderCapability,
)
from infobim._2d.plugin.capability.loader.viewer_session import (
    DxfViewerSessionOpenedCapability,
)


class DxfAnnotationCapabilities:
    """
    The capabilities InfoBIM hands OntoBDC's annotation creation for a DXF.

    The creation of an annotation from points asks, for each interactive
    state, which capability the request maps to the MIME type of the file.
    InfoBIM answers with its 2D viewer: it loads the drawing, opens the
    window, captures the points, asks for the details and closes the window.
    """

    DXF_MIME: ClassVar[str] = "image/vnd.dxf"

    CAPABILITIES_BY_KEY: ClassVar[Dict[str, Type[CapabilityPort]]] = {
        "drawable_document_capability": DxfDocumentLoaderCapability,
        "drawable_file_viewer_capability": DxfViewerSessionOpenedCapability,
        "points_captured_capability": DxfAnnotationPointsCapability,
        "annotation_details_capability": DxfAnnotationDetailsCapability,
    }

    @classmethod
    def apply(cls, context: CliContextPort) -> None:
        """
        Map, in the context, the DXF MIME type to each of the capabilities.
        """
        key: str
        capability: Type[CapabilityPort]
        for key, capability in cls.CAPABILITIES_BY_KEY.items():
            context.set_parameter_value(key, {cls.DXF_MIME: capability})
