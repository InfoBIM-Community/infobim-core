from typing import Any, ClassVar, Dict, List, Tuple, Type

from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CommandLoader
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse


class ProjectComponentBaseCommand(CliCommandPort, LoggerAwarePort):
    """
    Entry-point command shown when running ``infobim project``.

    Single responsibility: list the commands registered under the
    ``project`` logical component of InfoBIM (attach, select,
    inspect, refresh, dataset CRUD, …). The project-listing behaviour
    previously wired here now lives in ``ProjectListCommand`` in
    ``list.py`` so command inventory and container enumeration are
    two separate classes with strictly disjoint responsibilities.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_component_base",
        logical_component="project",
        description="Base project component command handler.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--help",
                    "-h",
                ],
                "description": (
                    "Print the tree of commands registered under the "
                    "``project`` logical component of InfoBIM."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "project"
    EXECUTABLE: ClassVar[str] = "infobim"
    ROOT_PACKAGE: ClassVar[str] = "infobim"
    HELP_FLAGS: ClassVar[List[str]] = ["--help", "-h"]
    LIST_FLAGS: ClassVar[List[str]] = ["--list", "-l"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the bare ``infobim project`` entrypoint, optionally with
        ``--help`` / ``-h`` as the only other word.

        ``--list`` / ``-l`` is intentionally handled by
        ``ProjectListCommand`` and is rejected here so the two
        matchers never collide.
        """
        if not args or args[0] != ProjectComponentBaseCommand.COMPONENT:
            return False

        if any(flag in args for flag in ProjectComponentBaseCommand.LIST_FLAGS):
            return False

        return len(args) == 1 or (
            len(args) == 2 and args[1] in ProjectComponentBaseCommand.HELP_FLAGS
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
        command_args: List[str] = self._request.command_args
        if any(flag in command_args for flag in self.LIST_FLAGS):
            return False

        if not command_args:
            return True

        if len(command_args) == 1:
            return command_args[0] in self.HELP_FLAGS

        return False

    def run(self) -> HelpCommandResponse:
        component_commands: List[Tuple[str, Type[CliCommandPort]]] = [
            (self.COMPONENT, command_class)
            for command_class in CommandLoader(
                self.COMPONENT,
                self._logger,
                root_package=self.ROOT_PACKAGE,
            ).get_all()
        ]
        command_tree: str = CommandTreeAdapter(
            logger=self._logger,
            root_package=self.ROOT_PACKAGE,
            executable=self.EXECUTABLE,
            command_classes=component_commands,
        ).render()

        content: Dict[str, str] = {
            "Usage": f"{self.EXECUTABLE} {self.COMPONENT} [flags/parameters]",
            "Commands": command_tree,
        }

        return HelpCommandResponse(
            title="Project Commands",
            description="Available InfoBIM project-domain utilities.",
            content=content,
        )
