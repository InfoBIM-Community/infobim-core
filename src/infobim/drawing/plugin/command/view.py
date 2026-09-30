from typing import Any, ClassVar, Dict, List, Type
from pathlib import Path

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    InteractiveTreeCommandResponse,
)

from infobim.drawing.adapter.tree import DrawingViewTree
from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.project.adapter.contract import ProjectGuard
from infobim.drawing.domain.model.view import DrawingView
from infobim.drawing.plugin.machine.drawing_view_discovery.machine import (
    DrawingViewDiscoveryStateTransitionHandler,
)
from infobim.drawing.plugin.machine.interactive_drawing_view_discovery.machine import (
    InteractiveDrawingViewDiscoveryStateTransitionHandler,
)


class DrawingViewDiscoveryCommand(CliCommandPort):
    """
    Discover the Drawing Views of a sheet and extract each into its own DXF.

    Selection and binding follow the other project commands: the parameter
    stage binds the project (``--global-id``, or the current directory) and
    the drawing; the command checks the project, runs the Drawing View
    discovery machine and, once the machine modelled the sheet's
    relationships and they conform to SHACL, renders the views as a tree
    rooted at the sheet the user named, DWG or DXF.

    With ``-i``/``--interactive`` the interactive discovery machine runs
    instead: the same states and capabilities, ending in the view browser.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="drawing_view_discovery",
        logical_component="drawing",
        description=(
            "Discover the Drawing Views of a DXF or DWG sheet and extract each "
            "one into a DXF of its own inside the project."
        ),
        arguments=[
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select the project by the GlobalId carried by its "
                    "IfcProject. When omitted, resolve the project from the "
                    "current working directory."
                ),
            },
            {
                "accepts": ["--view"],
                "valued": True,
                "parameter": "file_open_path",
                "description": "DXF or DWG sheet whose Drawing Views are discovered.",
                "usage": (
                    "infobim drawing [--global-id <project-global-id>] "
                    "--view <sheet.dxf|sheet.dwg> [-i|--interactive]"
                ),
            },
            {
                "accepts": ["--interactive", "-i"],
                "valued": False,
                "description": (
                    "Browse the discovered Drawing Views in the interactive "
                    "Textual viewer, with a preview of the view under the "
                    "cursor (↑/↓ or click to navigate, q/Esc to exit)."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "drawing"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    VIEW_FLAG: ClassVar[str] = "--view"
    INTERACTIVE_FLAGS: ClassVar[List[str]] = ["--interactive", "-i"]

    GLOBAL_ID_KEY: ClassVar[str] = "global_id"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the Drawing View discovery at the CLI routing stage.
        """
        if not args or args[0] != DrawingViewDiscoveryCommand.COMPONENT:
            return False

        return DrawingViewDiscoveryCommand._matches(args[1:])

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
            DrawingViewContextKeys.CONTAINER_PATH
        )
        if not isinstance(project_path, str) or not project_path.strip():
            return False

        ProjectGuard.guard(
            Path(project_path).expanduser().resolve(),
            self._request.context.root_path,
        )

        return True

    def run(self) -> CommandResponse:
        """
        Run the Drawing View discovery machine and render the views it settled.
        """
        context: Any = self._request.context
        drawing: str = RequiredParameter.of(context, DrawingViewContextKeys.DRAWING_PATH)
        # A DWG is converted and the open-file path replaced by its DXF; the
        # sheet the user named stays the source the relationships model.
        context.set_parameter_value(
            DrawingViewContextKeys.DRAWING_SOURCE_PATH,
            str(Path(drawing).expanduser().resolve()),
        )
        interactive: bool = self._is_interactive(self._request.command_args)
        handler_type: Type[DrawingViewDiscoveryStateTransitionHandler] = (
            InteractiveDrawingViewDiscoveryStateTransitionHandler
            if interactive
            else DrawingViewDiscoveryStateTransitionHandler
        )
        result: Dict[str, Any] = handler_type(context).execute()
        views: List[DrawingView] = result[DrawingViewContextKeys.VIEWS]
        relationships: Dict[str, Any] = result[DrawingViewContextKeys.RELATIONSHIPS]
        description: str = (
            f"Found {len(views)} Drawing Views in {Path(drawing).name}."
            if views
            else f"No Drawing View was detected in {Path(drawing).name}."
        )
        response_type: Type[CommandResponse] = (
            InteractiveTreeCommandResponse if interactive else CommandResponse
        )
        return response_type(
            title="Drawing Views",
            description=description,
            content={
                "global_id": context.get_parameter_value(self.GLOBAL_ID_KEY),
                "drawing": drawing,
                "views_directory": result[DrawingViewContextKeys.VIEWS_DIRECTORY],
                "views": [view.to_dict() for view in views],
                "relationships_modeled": True,
                "shacl_conforms": relationships["shacl_conforms"],
                "relationships": relationships,
                "tree": DrawingViewTree.of(Path(drawing).name, views),
            },
        )

    @staticmethod
    def _is_interactive(scoped_args: List[str]) -> bool:
        return any(
            flag in scoped_args for flag in DrawingViewDiscoveryCommand.INTERACTIVE_FLAGS
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --view with a value, and
        optionally --global-id with a value, in any order, with at most one
        of the interactive flags anywhere among them.
        """
        interactive: List[str] = [
            arg
            for arg in scoped_args
            if arg in DrawingViewDiscoveryCommand.INTERACTIVE_FLAGS
        ]
        if len(interactive) > 1:
            return False
        scoped_args = [
            arg
            for arg in scoped_args
            if arg not in DrawingViewDiscoveryCommand.INTERACTIVE_FLAGS
        ]
        flags: List[str] = [
            DrawingViewDiscoveryCommand.VIEW_FLAG,
            DrawingViewDiscoveryCommand.SELECTOR_FLAG,
        ]
        if len(scoped_args) % 2 != 0:
            return False

        seen: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        if len(set(seen)) != len(seen) or any(flag not in flags for flag in seen):
            return False
        if any(not value.strip() or value.startswith("--") for value in values):
            return False

        return DrawingViewDiscoveryCommand.VIEW_FLAG in seen
