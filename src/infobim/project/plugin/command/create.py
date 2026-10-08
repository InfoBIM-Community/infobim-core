from typing import Any, ClassVar, Dict, List
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.slug import TitleSlug
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from infobim.project.plugin.command.refresh import ProjectRefreshCommand
from infobim.project.plugin.machine.project_create.machine import ProjectCreateStateTransitionHandler


class ProjectCreateCommand(CliCommandPort, LoggerAwarePort):
    """
    Command for creating a new InfoBIM project with the given name.

    A project is an OntoBDC container that carries the reserved InfoBIM
    dataset and the IfcProject the model hangs from, so creating one runs
    the container's own creation steps and then InfoBIM's own — one machine,
    declared once, that ends at a project rather than at a container.

    The creation machine only puts the project's parts in place; it does not
    bring them to the state ``project --health`` verifies (the reserved
    dataset's directories and facade, the Data Package, the RO-Crate
    manifest). So once the project exists, the command runs the same
    refresh ``project --refresh`` runs, and a new project is born healthy.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_create",
        logical_component="project",
        description="Create a new InfoBIM Project with the given name.",
        arguments=[
            {
                "accepts": [
                    "--create",
                ],
                "valued": True,
                "description": (
                    "Title of the new InfoBIM project to create. A "
                    "filesystem slug is derived from this title and used "
                    "as the container folder name; the pipeline then "
                    "writes the container metadata, initializes the "
                    "reserved InfoBIM dataset and registers the project "
                    "in the storage index."
                ),
                "type": "str",
            },
        ],
    )

    CREATE_FLAG: ClassVar[str] = "--create"
    COMPONENT: ClassVar[str] = "project"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the project creation command at the CLI routing stage.
        """
        return (
            len(args) == 3
            and args[0] == ProjectCreateCommand.COMPONENT
            and args[1] == ProjectCreateCommand.CREATE_FLAG
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Any = None

    @property
    def log_strategy(self) -> Any:
        return self._log_strategy

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        command_args: List[str] = self._request.command_args
        if not (
            len(command_args) == 2
            and command_args[0] == self.CREATE_FLAG
            and bool(command_args[1].strip())
        ):
            return False

        project_title: str = command_args[1].strip()
        project_slug: str = TitleSlug.of(project_title)
        if not project_slug:
            raise CliCommandArgumentException(
                f"Invalid project name: {project_title}. It must contain at "
                f"least one letter or digit."
            )

        project_path: Path = Path(project_slug).resolve()
        self._request.context.delete_parameter("dataset_path")
        self._request.context.set_parameter_value(
            "container_title",
            project_title,
        )
        self._request.context.set_parameter_value(
            "container_path",
            str(project_path),
        )

        return True

    def run(self) -> CommandResponse:
        """
        Drive the target path all the way to being an InfoBIM project, then
        refresh it.
        """
        handler: ProjectCreateStateTransitionHandler = (
            ProjectCreateStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )
        create_response: CommandResponse = handler.execute()
        if isinstance(create_response, ExceptionCommandResponse):
            return create_response

        refresh_response: CommandResponse = self._refresh()
        if isinstance(refresh_response, ExceptionCommandResponse):
            return refresh_response

        refresh_content: Dict[str, Any] = refresh_response.content or {}
        create_response.content = {
            **(create_response.content or {}),
            "refresh_container_visited_states": refresh_content.get(
                "container_visited_states", []
            ),
            "refresh_project_visited_states": refresh_content.get(
                "project_visited_states", []
            ),
        }

        return create_response

    def _refresh(self) -> CommandResponse:
        """
        Run the refresh ``project --refresh`` runs on the project just created.

        The context already names the project through ``container_path``,
        which is all the refresh stages read, so the refresh command is run
        directly, past its own argument check.
        """
        refresh_command: ProjectRefreshCommand = ProjectRefreshCommand(
            self._request
        )
        if self._log_strategy is not None:
            refresh_command.set_log_strategy(self._log_strategy)

        return refresh_command.run()
