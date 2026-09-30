from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import TreeCommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.shared.adapter.parameter import RequiredParameter

from infobim.project.adapter.tree import ProjectTree
from infobim.project.adapter.contract import ProjectGuard

from ...adapter.element_discovery import ThreeDElementDiscovery
from ...adapter.tree import ThreeDElementTree


class ThreeDInspectCommand(CliCommandPort):
    """
    Lists every file a Project, and every dataset it holds, carries that
    the offline 3D viewer can render: *.ifcx and *.ifc-3d, wherever
    inside the Project's own tree or any of its datasets they sit.

    ThreeDElementDiscovery is the same discovery the offline viewer's
    "3D inspect" tab uses (see ThreeDElementTreeInjectedCapability), so
    the CLI and the viewer never disagree about which elements exist or
    what each one is titled.

    --global-id and --inspect are independent flags, not positions:
    either may come first (see "Matching arguments without position" in
    the docs for why this must hold once a command combines a selector
    with an action). --inspect is what disambiguates this from a bare
    `infobim 3d --global-id <id>`, which already opens the offline
    viewer for that same Project.

    The selector is --global-id, not a command-local flag of its own:
    every other command that selects a Project by identifier (`infobim
    3d` itself, `project --inspect`, `project --health`, ...) already
    uses that name, and resolving it is GlobalIdStrategy's job --
    declaring the same "global_id" parameter here is what reuses that
    resolution instead of duplicating it.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="three_d_inspect",
        logical_component="3d",
        description=(
            "List every *.ifcx/*.ifc-3d file a Project and its datasets hold."
        ),
        arguments=[
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "The Project to list renderable 3D elements for, by "
                    "the GlobalId of its IfcProject or its container id."
                ),
                "usage": (
                    "infobim 3d --inspect | "
                    "infobim 3d --global-id <GlobalId-or-container-id> --inspect"
                ),
            },
            {
                # No flag on purpose: the command also answers with no
                # selector at all, acting on the Project of the current
                # directory -- the same fallback ThreeDCommand, project
                # --health and every other selector+action command in
                # this codebase already give a bare invocation.
                "accepts": [],
                "valued": True,
                "parameter": "container",
                "description": (
                    "The Project the command acts on when no GlobalId is "
                    "given, resolved from the current directory."
                ),
            },
            {
                "accepts": ["--inspect"],
                "description": "List the Project's renderable 3D elements.",
                "usage": (
                    "infobim 3d --inspect | "
                    "infobim 3d --global-id <GlobalId-or-container-id> --inspect"
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "3d"
    SELECTOR_FLAG: ClassVar[str] = "--global-id"
    INSPECT_FLAG: ClassVar[str] = "--inspect"
    PROJECT_PATH_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match this command at the CLI routing stage.
        """
        if not args or args[0] != ThreeDInspectCommand.COMPONENT:
            return False

        return ThreeDInspectCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        if not self._matches(self._request.command_args):
            return False

        project_path_value: Any = self._request.context.get_parameter_value(
            self.PROJECT_PATH_KEY
        )
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise CliCommandArgumentException(
                "No InfoBIM Project was resolved. Run the command inside "
                "a Project or pass --global-id <GlobalId-or-container-id>."
            )

        project_path: Path = Path(project_path_value).expanduser().resolve()
        ProjectGuard.guard(project_path, self._request.context.root_path)

        return True

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --inspect with an optional
        --global-id <id>, in either order.

        The selector and the action are independent flags, not
        positions -- and the selector is optional: with none given, the
        Project resolves from the current directory instead, the same
        as every other selector+action command in this codebase.
        """
        if ThreeDInspectCommand.INSPECT_FLAG not in scoped_args:
            return False

        remaining: List[str] = list(scoped_args)
        remaining.remove(ThreeDInspectCommand.INSPECT_FLAG)
        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == ThreeDInspectCommand.SELECTOR_FLAG
            and bool(remaining[1].strip())
        )

    def run(self) -> TreeCommandResponse:
        project_path: Path = Path(
            RequiredParameter.of(self._request.context, self.PROJECT_PATH_KEY)
        ).expanduser().resolve()

        elements: List[Dict[str, str]] = ThreeDElementDiscovery.of(project_path)

        lang: str = (
            self._request.context.language
            if self._request.context.language is not None
            else ThreeDElementTree.DEFAULT_LANGUAGE
        )
        tree: Dict[str, Any] = ProjectTree.of(
            project_path,
            branches=[ThreeDElementTree.of(elements, lang)],
        )

        return TreeCommandResponse(
            title="InfoBIM 3D Elements",
            description=(
                f"Found {len(elements)} renderable 3D element(s) in "
                f"the Project «{project_path.name}» and its datasets."
            ),
            content={"tree": tree},
        )
