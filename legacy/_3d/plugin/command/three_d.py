from typing import Any, ClassVar, List
from pathlib import Path
import webbrowser

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from ...vendor import ViewerAsset
from ...adapter.viewer import OfflineViewer
from ..machine.three_d_view.state import ThreeDViewContextKeys
from ..machine.three_d_view.machine import ThreeDViewStateTransitionHandler
from infobim.project.adapter.contract import ProjectGuard


class ThreeDCommand(CliCommandPort):
    """Open the offline InfoBIM 3D viewer for one InfoBIM Project, empty.

    Resolving and validating the Project is this command's own
    precondition; the machine it drives loads nothing from the Project
    beyond its IfcProject, staged as JSON-LD for the page. The viewer
    opens with no model, the same blank state its own "open local IFCX
    files" picker starts from, and loading the Project's own drawings
    into it is a separate concern to add back deliberately, not
    something opening the viewer should do on its own.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="three_d",
        logical_component="3d",
        description="Open the offline InfoBIM 3D viewer for a Project.",
        arguments=[
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Open the Project whose IfcProject carries the given GlobalId."
                ),
                "usage": "infobim 3d | infobim 3d --global-id <GlobalId>",
            },
            {
                "accepts": [],
                "valued": True,
                "parameter": "container",
                "description": (
                    "The Project in the current directory when no GlobalId is given."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "3d"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    PROJECT_PATH_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if args == [ThreeDCommand.COMPONENT]:
            return True

        return (
            len(args) == 3
            and args[0] == ThreeDCommand.COMPONENT
            and args[1] == ThreeDCommand.SELECTOR_FLAG
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        if command_args:
            if not (
                len(command_args) == 2
                and command_args[0] == self.SELECTOR_FLAG
                and bool(str(command_args[1]).strip())
            ):
                return False

        project_path_value: Any = self._request.context.get_parameter_value(
            self.PROJECT_PATH_KEY
        )
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise CliCommandArgumentException(
                "No InfoBIM Project was resolved. Run the command inside a Project "
                "or pass --global-id <GlobalId>."
            )

        project_path: Path = Path(project_path_value).expanduser().resolve()
        ProjectGuard.guard(project_path, self._request.context.root_path)

        viewer_path: Path = ViewerAsset.path()
        if not viewer_path.is_file():
            raise CliCommandArgumentException(
                "The installed InfoBIM package is missing its offline viewer. "
                "Rebuild with `python -m infobim._3d.vendor` and reinstall InfoBIM."
            )

        return True

    def run(self) -> CommandResponse:
        project_path: Path = Path(
            RequiredParameter.of(self._request.context, self.PROJECT_PATH_KEY)
        ).expanduser().resolve()

        handler: ThreeDViewStateTransitionHandler = ThreeDViewStateTransitionHandler(
            context=self._request.context,
        )
        visited_states: List[str] = handler.execute()
        ifc_project_jsonld: Any = self._request.context.get_parameter_value(
            ThreeDViewContextKeys.IFC_PROJECT_JSONLD_KEY
        )
        project_tree: Any = self._request.context.get_parameter_value(
            ThreeDViewContextKeys.PROJECT_TREE_KEY
        )
        three_d_element_tree: Any = self._request.context.get_parameter_value(
            ThreeDViewContextKeys.THREE_D_ELEMENT_TREE_KEY
        )

        viewer_path: Path = OfflineViewer.launch_page(
            {
                "ifcProject": ifc_project_jsonld,
                "language": self._request.context.language,
                "projectTree": project_tree,
                "threeDElementTree": three_d_element_tree,
            }
        )
        viewer_uri: str = viewer_path.as_uri()

        opened: bool = webbrowser.open_new_tab(viewer_uri)
        if not opened:
            raise RuntimeError(f"The default browser could not be opened. Offline launch page: {viewer_path}")

        return CommandResponse(
            title="InfoBIM 3D",
            description="Opened the offline IFCX viewer for the selected Project.",
            content={
                "project": str(project_path),
                "viewer": str(viewer_path),
                "opened": opened,
                "visited_states": visited_states,
            },
        )
