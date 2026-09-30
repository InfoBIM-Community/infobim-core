"""Builds the Project's 3D-elements tree and stages it for the viewer."""

from typing import Any, ClassVar, Dict, List
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from ....adapter.element_discovery import ThreeDElementDiscovery
from ....adapter.tree import ThreeDElementTree
from ...machine.three_d_view.state import ThreeDViewContextKeys, ThreeDViewProcessState


class ThreeDElementTreeInjectedCapability(TransactionCapability):
    """
    Builds the Project's 3D-elements tree and stages it for the viewer.

    This is the same tree `infobim 3d --inspect` renders, built by the
    same ThreeDElementDiscovery the command reads from; this capability
    only adapts that read to the capability contract, and hands the
    result to the command through the context rather than through its
    own return value -- the state machine that runs this capability
    discards what it returns, the same way it does for every other
    transition capability in this codebase.

    Unlike the CLI's own tree, every IFCX element here also carries its
    own parsed document (see ThreeDElementDiscovery.with_documents): the
    offline viewer has no way to fetch a file by path once it is
    launched, so a "3D inspect" tree node that a click should load into
    the scene must already carry everything ViewerModels.add needs.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.3d.plugin.capability.transformation.target."
            "three_d_element_tree_injected"
        ),
        version="0.1.0",
        name="3D Element Tree Injected",
        description=(
            "Build the Project's renderable 3D elements tree and stage "
            "it for the offline 3D viewer page."
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
                "three_d_element_tree": {"type": "object"},
            },
            "required": ["three_d_element_tree"],
        },
    )

    def label(self, lang: str = "en") -> str:
        return "3D Element Tree Injected"

    def description(self, lang: str = "en") -> str:
        return (
            "Builds the Project's renderable 3D elements tree and stages "
            "it for the offline 3D viewer page."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Build the 3D-elements tree and place it on the context for the
        command to embed in the viewer page.
        """
        container_value: Any = context.get_parameter_value(
            self.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise ValueError(
                "The container path is missing from the command context."
            )

        project_path: Path = Path(container_value).expanduser().resolve()
        lang: str = (
            context.language
            if context.language is not None
            else ThreeDElementTree.DEFAULT_LANGUAGE
        )
        elements: List[Dict[str, Any]] = ThreeDElementDiscovery.with_documents(
            project_path
        )
        tree: Dict[str, Any] = ThreeDElementTree.of(elements, lang)
        context.set_parameter_value(
            ThreeDViewContextKeys.THREE_D_ELEMENT_TREE_KEY, tree
        )

        return {
            "resulting_state": ThreeDViewProcessState.THREE_D_ELEMENT_TREE_INJECTED,
            "three_d_element_tree": tree,
        }
