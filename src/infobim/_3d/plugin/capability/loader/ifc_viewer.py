from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim._3d.adapter.viewer import IfcQuick3DViewer
from infobim._3d.adapter.quick3d import IfcElementGeometry


class IfcViewerCapability(DataLoaderCapability):
    """Open the Qt Quick 3D viewer with the IFC element geometries in the context."""

    GEOMETRIES_KEY: ClassVar[str] = "ifc_quick3d_geometries"
    PICKED_KEY: ClassVar[str] = "ifc_picked_global_ids"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._3d.plugin.capability.loader.ifc_viewer",
        version="1.0.0",
        name="IFC 3D Viewer",
        description=(
            "Open a navigable Qt Quick 3D viewer with one pickable Model per "
            "IFC element geometry in the context."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "3d", "ifc", "viewer", "qt", "read-only"],
        supported_languages=["en"],
        input_schema={
            "type": "object",
            "properties": {
                GEOMETRIES_KEY: {"type": list, "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                PICKED_KEY: {"type": list, "required": True},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "IFC 3D Viewer"

    def description(self, lang: str = "en") -> str:
        return "Opens the IFC element geometries in the Qt Quick 3D viewer."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        geometries: List[IfcElementGeometry] = context.get_parameter_value(
            self.GEOMETRIES_KEY
        )
        picked: List[str] = IfcQuick3DViewer().show(geometries)
        context.set_parameter_value(self.PICKED_KEY, picked)
        return {self.PICKED_KEY: picked}
