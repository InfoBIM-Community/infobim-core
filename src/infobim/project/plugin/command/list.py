from typing import ClassVar, Dict, List, Optional

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    ListCommandResponse,
)
from infobim.project.adapter.contract import ProjectGuard


class ProjectListCommand(CliCommandPort):
    """
    Lists the registered InfoBIM projects.

    Single responsibility: enumerate storage containers matching the
    InfoBIM Project contract. Listing is the one place where the
    contract cannot be enforced by refusing: a registered container
    that is not a project is not an error, it simply is not a project,
    and belongs out of the answer rather than in an exception.

    Component-command inventory (the default ``infobim project``
    behaviour) lives in ``ProjectComponentBaseCommand`` in ``base.py``,
    never here — one class = one concern.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_list",
        logical_component="project",
        description="List every storage container registered as an InfoBIM Project.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--list",
                    "-l",
                ],
                "description": (
                    "Print the list of every storage container currently "
                    "registered as an InfoBIM Project. Containers that do "
                    "not match the Project contract are excluded from the "
                    "result instead of being reported as errors."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "project"
    LIST_FLAGS: ClassVar[List[str]] = ["--list", "-l"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match ``infobim project [--list|-l]`` at the CLI routing stage.

        ``--list`` / ``-l`` is required here; bare ``project`` belongs
        to the component help command and is explicitly rejected so
        matchers stay mutually exclusive.
        """
        if not args or args[0] != ProjectListCommand.COMPONENT:
            return False

        if not any(flag in args for flag in ProjectListCommand.LIST_FLAGS):
            return False

        remaining: List[str] = [
            arg for arg in args
            if arg != ProjectListCommand.COMPONENT
            and arg not in ProjectListCommand.LIST_FLAGS
        ]
        return not remaining

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        return (
            len(command_args) == 1
            and command_args[0] in self.LIST_FLAGS
        )

    def run(self) -> CommandResponse:
        """
        List every registered container that satisfies the Project contract.
        """
        try:
            projects: List[Dict[str, Optional[str]]] = (
                ProjectGuard.registered_projects(
                    self._request.context.root_path,
                )
            )

        except Exception as error:
            return ExceptionCommandResponse(
                title="Failed to List Projects",
                description=(
                    f"An error occurred while reading the storage index: "
                    f"{error}"
                ),
                content={"projects": [], "error": str(error)},
            )

        return ListCommandResponse(
            title="InfoBIM Projects",
            description=f"Found {len(projects)} project(s) in the storage.",
            content={"projects": projects},
        )
