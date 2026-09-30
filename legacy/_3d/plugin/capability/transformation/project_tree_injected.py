from typing import Any, ClassVar, Dict, Optional, Type
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.capability import CapabilityPort

from ...machine.three_d_view.state import ThreeDViewContextKeys, ThreeDViewProcessState
from infobim.project.adapter.tree import ProjectTree


class ProjectTreeInjectedCapability(TransactionCapability):
    """
    Builds the Project's inspect tree and stages it for the viewer.

    This is the same tree `infobim project --inspect` renders, built by
    the same ProjectTree the command reads from; this capability only
    adapts that read to the capability contract, and hands the result to
    the command through the context rather than through its own return
    value -- the state machine that runs this capability discards what
    it returns, the same way it does for every other transition
    capability in this codebase.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    DRAWING_CAPABILITY_ID: ClassVar[str] = (
        "org.infobim.drawing.plugin.capability.loader.container"
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.3d.plugin.capability.transformation.target."
            "project_tree_injected"
        ),
        version="0.1.0",
        name="Project Tree Injected",
        description=(
            "Build the Project's inspect tree and stage it for the "
            "offline 3D viewer page."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "3d", "project", "viewer"],
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
                "project_tree": {"type": "object"},
            },
            "required": ["project_tree"],
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Project Tree Injected"

    def description(self, lang: str = "en") -> str:
        return (
            "Builds the Project's inspect tree and stages it for the "
            "offline 3D viewer page."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Build the Project's inspect tree and place it on the context for
        the command to embed in the viewer page.
        """
        container_value: Any = context.get_parameter_value(
            self.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise ValueError(
                "The container path is missing from the command context."
            )

        project_path: Path = Path(container_value).expanduser().resolve()
        tree: Dict[str, Any] = ProjectTree.of(
            project_path, branches=[self._drawing_tree(context)]
        )
        context.set_parameter_value(
            ThreeDViewContextKeys.PROJECT_TREE_KEY, tree
        )

        return {
            "resulting_state": ThreeDViewProcessState.PROJECT_TREE_INJECTED,
            "project_tree": tree,
        }

    def _drawing_tree(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Load the drawing branch through the capability registry.

        Mirrors ProjectInspectCommand's own _drawing_tree: `infobim
        project --inspect` and this capability must show the same tree,
        so both resolve it the same way -- by id, never by importing the
        drawing capability's class directly.
        """
        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=("infobim",)
        ).get(self.DRAWING_CAPABILITY_ID)
        if capability_type is None:
            raise ValueError(
                f"Drawing capability not found: {self.DRAWING_CAPABILITY_ID}"
            )

        capability: CapabilityPort = capability_type()
        result: Dict[str, Any] = capability.execute(context)
        if "drawings" not in result:
            raise ValueError("Drawing capability returned no drawings tree.")

        drawings: Any = result["drawings"]
        if not isinstance(drawings, dict):
            raise ValueError("Drawing capability returned an invalid drawings tree.")

        return drawings
