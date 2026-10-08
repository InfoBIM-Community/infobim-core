from typing import Any, ClassVar, Dict, List, Optional, Type
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.cli.component.widget.itree import InteractiveTreeWidget
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import InteractiveTreeCommandResponse
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport

from infobim._3d.adapter.taxonomy import IfcMimeTaxonomy
from infobim.project.adapter.tree import ProjectTree
from infobim._2d.adapter.capability import TwoDCapabilityLoader
from infobim._3d.adapter.capability import ThreeDCapabilityLoader
from infobim.project.adapter.contract import ProjectGuard


class ProjectInteractiveInspectCommand(CliCommandPort):
    """
    Shows a project as the INTERACTIVE Textual tree of what it holds.

    This command owns exactly one responsibility: launching the Textual
    TUI that the user navigates with keyboard and mouse. Because it
    takes terminal ownership, it returns an InteractiveTreeCommandResponse
    so that the outer CLI entrypoint (cli/__init__.py) skips markdown
    rendering — a response that this class exclusively produces.

    The static, pipe-friendly, rendering is the sole responsibility of
    ProjectInspectCommand so that each class has a single reason to
    change and a single response contract (SRP).
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_interactive_inspect",
        logical_component="project",
        description=(
            "Inspect a registered InfoBIM Project in the interactive "
            "Textual tree viewer."
        ),
        arguments=[
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select which project to inspect, by the GlobalId "
                    "carried by its IfcProject or by the container "
                    "storage identifier. When omitted, resolve the "
                    "project from the current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": ["--inspect"],
                "description": (
                    "Open the project's registered metadata along with "
                    "a tree summarizing its reserved InfoBIM dataset, "
                    "linkset and any additional datasets inside the "
                    "interactive Textual viewer."
                ),
            },
            {
                "accepts": ["--interactive", "-i"],
                "valued": False,
                "description": (
                    "Open the project tree in the interactive Textual "
                    "viewer with keyboard/mouse collapse and expand, "
                    "native search, keyboard navigation (e=expand all, "
                    "c=collapse all, q=quit, ↑/↓=navigate, "
                    "Enter/Space=toggle a node)."
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
    INFO_CAPABILITY_ID: ClassVar[str] = (
        "org.infobim.project.plugin.capability.loader.info"
    )
    INFO_TREE_KEY: ClassVar[str] = "info"
    MODELS_TREE_KEY: ClassVar[str] = "models"
    DRAWINGS_TREE_KEY: ClassVar[str] = "drawings"
    OPEN_FILE_CAPABILITY_IDS_BY_MIME: ClassVar[Dict[str, str]] = {
        "image/vnd.dwg": "org.infobim._2d.plugin.capability.loader.pyside6",
        "image/vnd.dxf": "org.infobim._2d.plugin.capability.loader.pyside6",
        **{
            mime: "org.infobim._3d.plugin.capability.loader.ifc_open_file"
            for mime in IfcMimeTaxonomy.SUPPORTED
        },
    }

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """Match the interactive project inspection at the CLI routing stage."""
        if not args or args[0] != ProjectInteractiveInspectCommand.COMPONENT:
            return False

        return ProjectInteractiveInspectCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """Check if the command is valid."""
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
        if not any(
            flag in scoped_args
            for flag in ProjectInteractiveInspectCommand.INSPECT_FLAGS
        ):
            return False

        if not any(
            flag in scoped_args
            for flag in ProjectInteractiveInspectCommand.INTERACTIVE_FLAGS
        ):
            return False

        remaining: List[str] = list(scoped_args)
        for inspect_flag in ProjectInteractiveInspectCommand.INSPECT_FLAGS:
            if inspect_flag in remaining:
                remaining.remove(inspect_flag)
                break
        for interactive_flag in ProjectInteractiveInspectCommand.INTERACTIVE_FLAGS:
            if interactive_flag in remaining:
                remaining.remove(interactive_flag)
                break
        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == ProjectInteractiveInspectCommand.SELECTOR_FLAG
            and bool(remaining[1].strip())
        )

    def run(self) -> InteractiveTreeCommandResponse:
        """Render the selected project inside the interactive Textual viewer."""
        project_path: Path = Path(
            RequiredParameter.of(self._request.context, self.PROJECT_PATH_KEY)
        ).expanduser().resolve()

        info_branch: Dict[str, Any] = self._load_tree(
            self.INFO_CAPABILITY_ID,
            self.INFO_TREE_KEY,
        )
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
            branches=[info_branch, models_branch, drawings_branch],
        )

        widget = InteractiveTreeWidget()
        widget.title = "InfoBIM Project"
        widget.description = f"Tree view of the Project «{project_path.name}»."
        widget.root = tree
        widget.content_root_path = project_path
        widget.plugin_root_packages = ("ontobdc", "infobim")

        context_language: Any = getattr(self._request.context, "language", None)
        if isinstance(context_language, str) and context_language.strip():
            widget.language = context_language

        self._request.context.set_parameter_value(
            OpenFileChainSupport.CAPABILITY_BY_MIME_KEY,
            self._open_file_capabilities(),
        )
        widget.context = self._request.context
        widget.show()

        return InteractiveTreeCommandResponse(
            title="InfoBIM Project",
            description=f"Tree view of the Project «{project_path.name}».",
            content={"tree": tree},
        )

    def _open_file_capabilities(self) -> Dict[str, Type[CapabilityPort]]:
        """Resolve the internal 2D/3D capability that opens each MIME type."""
        capabilities_by_id: Dict[str, Type[CapabilityPort]] = {
            capability_type.METADATA.id: capability_type
            for loader in (
                TwoDCapabilityLoader(NullLogRepository()),
                ThreeDCapabilityLoader(NullLogRepository()),
            )
            for capability_type in loader.get_all(OpenFileChainSupport)
        }

        capabilities_by_mime: Dict[str, Type[CapabilityPort]] = {}
        mime_type: str
        capability_id: str
        for mime_type, capability_id in self.OPEN_FILE_CAPABILITY_IDS_BY_MIME.items():
            if capability_id not in capabilities_by_id:
                raise ValueError(f"Capability not found: {capability_id}")
            capabilities_by_mime[mime_type] = capabilities_by_id[capability_id]

        return capabilities_by_mime

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
