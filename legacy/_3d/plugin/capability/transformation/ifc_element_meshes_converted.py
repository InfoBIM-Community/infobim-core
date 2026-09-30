"""Converts the Project's IFC element geometry into IFCX meshes for the viewer."""

from typing import Any, ClassVar, Dict, List
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from ....adapter.ifc_mesh import IfcElementMeshConverter
from ...machine.three_d_view.state import ThreeDViewContextKeys, ThreeDViewProcessState


class IfcElementMeshesConvertedCapability(TransactionCapability):
    """
    Converts every IFC element that has geometry into an IFCX mesh.

    The viewer draws IFCX and a Project's geometry lives in its IFC
    models, so the elements have to be said in the other format before
    anything can draw them. This runs first, before the trees the viewer
    page carries are built, so a mesh written now is an element the tree
    built after it already lists.

    Which IFC models are read is what the Project's RO-Crate declares,
    and only that: a file the crate does not state is not a model of the
    Project, however much it looks like one from the directory.

    What it produces is on disk — one mesh per element, its linkset
    beside it — so what is staged on the context is the record of what
    was written, not the meshes themselves: the page reads them through
    the 3D element tree, the same way it reads a drawing's.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.3d.plugin.capability.transformation.target."
            "ifc_element_meshes_converted"
        ),
        version="0.1.0",
        name="IFC Element Meshes Converted",
        description=(
            "Convert every IFC element the Project declares geometry for "
            "into an IFCX mesh of its own, declared by its own linkset."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "3d", "ifc", "ifcx", "mesh"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_element_meshes": {"type": "object"},
            },
            "required": ["ifc_element_meshes"],
        },
    )

    def label(self, lang: str = "en") -> str:
        return "IFC Element Meshes Converted"

    def description(self, lang: str = "en") -> str:
        return (
            "Converts every IFC element with geometry into an IFCX mesh "
            "the offline 3D viewer can draw."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Convert the elements and stage what was written for this launch.
        """
        container_value: Any = context.get_parameter_value(
            self.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise ValueError(
                "The container path is missing from the command context."
            )

        project_path: Path = Path(container_value).expanduser().resolve()
        meshes: List[Dict[str, str]] = IfcElementMeshConverter.convert(project_path)
        context.set_parameter_value(
            ThreeDViewContextKeys.IFC_ELEMENT_MESHES_KEY, meshes
        )

        return {
            "resulting_state": ThreeDViewProcessState.IFC_ELEMENT_MESHES_CONVERTED,
            "ifc_element_meshes": meshes,
        }
