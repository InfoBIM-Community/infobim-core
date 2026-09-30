from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Type

from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import TreeCommandResponse
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.project.adapter.tree import ProjectTree
from infobim.project.adapter.contract import ProjectGuard


class ProjectInspectCommand(CliCommandPort):
    """
    Shows a project as the static tree of what it holds.

    This is the one project command that does not stand for a container
    command. Inspecting a container answers what OntoBDC knows about it —
    its identifier, its title, the directory it is — and a reader of
    InfoBIM is asking something else: what this project holds, read from
    its IfcProject down. The tree is InfoBIM's own, so the command that
    renders it is too.

    Selection is the same as every other project command's: the Project of
    the current directory, or the one the GlobalId names.

    Responsibility boundary (Single Responsibility): this command owns
    only the static, pipe-friendly rendering that returns a plain
    TreeCommandResponse. The interactive Textual TUI lives in its own
    dedicated command class (ProjectInteractiveInspectCommand) so that
    each class has one reason to change and one response contract.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_inspect",
        logical_component="project",
        description="Inspect a registered InfoBIM Project.",
        arguments=[
            {
                "accepts": [
                    "--global-id",
                ],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select which project to inspect, by the GlobalId "
                    "carried by its IfcProject or by the container "
                    "storage identifier. When omitted, resolve the "
                    "project from the current working directory."
                ),
            },
            {
                "accepts": ["--inspect"],
                "description": (
                    "Print the project's registered metadata along with "
                    "a static tree summarizing its reserved InfoBIM "
                    "dataset, linkset and any additional datasets."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "project"
    INSPECT_FLAGS: ClassVar[List[str]] = ["--inspect"]
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    INTERACTIVE_FLAGS: ClassVar[List[str]] = ["--interactive", "-i"]
    PROJECT_PATH_KEY: ClassVar[str] = "container_path"
    IFC_MODELS_CAPABILITY_ID: ClassVar[str] = (
        "org.infobim.ifc.plugin.capability.loader.container.models"
    )
    DRAWINGS_CAPABILITY_ID: ClassVar[str] = (
        "org.infobim.drawing.plugin.capability.loader.container"
    )
    MODELS_TREE_KEY: ClassVar[str] = "models"
    DRAWINGS_TREE_KEY: ClassVar[str] = "drawings"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the project inspection at the CLI routing stage.
        """
        if not args or args[0] != ProjectInspectCommand.COMPONENT:
            return False

        return ProjectInspectCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if not self._matches(self._request.command_args):
            return False

        project_path: Any = self._request.context.get_parameter_value(
            self.PROJECT_PATH_KEY
        )
        if not isinstance(project_path, str) or not project_path.strip():
            return False

        ProjectGuard.guard(
            Path(project_path).expanduser().resolve(),
            self._request.context.root_path,
        )

        return True

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are a STATIC --inspect request.

        Mutually exclusive with ProjectInteractiveInspectCommand: this
        matcher rejects inputs that carry --interactive (or its short
        alias -i) because that presentation mode is the dedicated
        interactive command's sole responsibility.
        """
        if not any(flag in scoped_args for flag in ProjectInspectCommand.INSPECT_FLAGS):
            return False

        if any(flag in scoped_args for flag in ProjectInspectCommand.INTERACTIVE_FLAGS):
            return False

        remaining: List[str] = list(scoped_args)
        for inspect_flag in ProjectInspectCommand.INSPECT_FLAGS:
            if inspect_flag in remaining:
                remaining.remove(inspect_flag)
                break
        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == ProjectInspectCommand.SELECTOR_FLAG
            and bool(remaining[1].strip())
        )

    def run(self) -> TreeCommandResponse:
        """
        Render the selected project as the static tree of what it holds.
        """
        project_path: Path = Path(
            RequiredParameter.of(self._request.context, self.PROJECT_PATH_KEY)
        ).expanduser().resolve()

        models_branch: Dict[str, Any] = self._load_tree(
            self.IFC_MODELS_CAPABILITY_ID,
            self.MODELS_TREE_KEY,
        )
        drawings_branch: Dict[str, Any] = self._load_tree(
            self.DRAWINGS_CAPABILITY_ID,
            self.DRAWINGS_TREE_KEY,
        )
        tree: Dict[str, Any] = ProjectTree.of(
            project_path,
            branches=[models_branch, drawings_branch],
        )

        return TreeCommandResponse(
            title="InfoBIM Project",
            description=f"Tree view of the Project «{project_path.name}».",
            content={"tree": tree},
        )

    def _load_tree(
        self,
        capability_id: str,
        tree_key: str,
    ) -> Dict[str, Any]:
        """Load one project-tree branch through the capability registry."""
        capability_type: Optional[Type[CapabilityPort]] = CapabilityLoader(
            root_packages=("infobim",)
        ).get(capability_id)
        if capability_type is None:
            raise ValueError(f"Capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        result: Dict[str, Any] = capability.execute(self._request.context)
        tree: Any = result.get(tree_key)
        if not isinstance(tree, dict):
            raise ValueError(
                f"Capability {capability_id} returned no valid {tree_key} tree."
            )

        return tree
