from typing import Any, ClassVar, List

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.container.domain.model.remote import RemoteContainerUrl

from infobim.project.plugin.machine.project_remote.machine import (
    ProjectRemoteStateTransitionHandler,
)


class ProjectRemoteCommand(CliCommandPort, LoggerAwarePort):
    """
    Command for connecting to a remote InfoBIM project by its URL.

    The URL points to the project's ``.obdc`` file. The command runs the
    same remote connection machine the OntoBDC container command runs,
    which downloads the file into the current directory. An address that
    is not an http or https URL is refused when the command is checked,
    and a download that fails raises.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_remote",
        logical_component="project",
        description="Connect to a remote InfoBIM Project by the URL of its file.",
        arguments=[
            {
                "accepts": [
                    "--remote",
                ],
                "valued": True,
                "description": (
                    "http or https URL of the remote InfoBIM project file "
                    "(.obdc). The file is downloaded into the current "
                    "directory; an existing file of the same name is not "
                    "overwritten."
                ),
                "type": "str",
            },
        ],
    )

    REMOTE_FLAG: ClassVar[str] = "--remote"
    COMPONENT: ClassVar[str] = "project"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the remote project command at the CLI routing stage.
        """
        return (
            len(args) == 3
            and args[0] == ProjectRemoteCommand.COMPONENT
            and args[1] == ProjectRemoteCommand.REMOTE_FLAG
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
            and command_args[0] == self.REMOTE_FLAG
            and bool(command_args[1].strip())
        ):
            return False

        remote_url: str = command_args[1].strip()
        if not RemoteContainerUrl.is_valid(remote_url):
            raise CliCommandArgumentException(
                f"Invalid remote project URL: {remote_url}. It must be an "
                f"http or https URL with a host."
            )

        self._request.context.set_parameter_value("remote_url", remote_url)

        return True

    def run(self) -> CommandResponse:
        """
        Drive the remote connection machine and report where it ended.
        """
        handler: ProjectRemoteStateTransitionHandler = (
            ProjectRemoteStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )

        return handler.execute()
