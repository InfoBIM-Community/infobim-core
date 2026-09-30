from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from ...machine.three_d_view.state import ThreeDViewContextKeys, ThreeDViewProcessState
from ...check.is_ifc_project_injected.hotfix import build_ifc_project_jsonld


class IfcProjectInjectedCapability(TransactionCapability):
    """
    Reads the Project's IfcProject and stages it as JSON-LD for the viewer.

    The read itself, including the ifc_project.ttl path and the JSON-LD
    serialization, lives in build_ifc_project_jsonld; this capability
    only adapts that read to the capability contract, and hands the
    result to the command through the context rather than through its
    own return value -- the state machine that runs this capability
    discards what it returns, the same way it does for every other
    transition capability in this codebase.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.3d.plugin.capability.transformation.target."
            "ifc_project_injected"
        ),
        version="0.1.0",
        name="IfcProject Injected",
        description=(
            "Read the Project's IfcProject and stage it as JSON-LD for "
            "the offline 3D viewer page."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "3d", "ifc", "viewer"],
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
                "ifc_project_jsonld": {"type": "object"},
            },
            "required": ["ifc_project_jsonld"],
        },
    )

    def label(self, lang: str = "en") -> str:
        return "IfcProject Injected"

    def description(self, lang: str = "en") -> str:
        return (
            "Reads the Project's IfcProject and stages it as JSON-LD for "
            "the offline 3D viewer page."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Read the Project's IfcProject and place it on the context as
        JSON-LD for the command to embed in the viewer page.
        """
        container_value: Any = context.get_parameter_value(
            self.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise ValueError(
                "The container path is missing from the command context."
            )

        project_path: Path = Path(container_value).expanduser().resolve()
        jsonld: Any = build_ifc_project_jsonld(project_path)
        context.set_parameter_value(
            ThreeDViewContextKeys.IFC_PROJECT_JSONLD_KEY, jsonld
        )

        return {
            "resulting_state": ThreeDViewProcessState.IFC_PROJECT_INJECTED,
            "ifc_project_jsonld": jsonld,
        }
