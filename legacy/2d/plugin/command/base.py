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


class TwoDBaseCommand(CliCommandPort, LoggerAwarePort):
    """Show the commands provided by the InfoBIM 2D component."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_base",
        logical_component="2d",
        description="Base 2D command handler.",
        depends_on=None,
    )

    COMPONENT: ClassVar[str] = "2d"
    EXECUTABLE: ClassVar[str] = "infobim"
    ROOT_PACKAGE: ClassVar[str] = "infobim"
    HELP_FLAGS: ClassVar[List[str]] = ["--help", "-h"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != TwoDBaseCommand.COMPONENT:
            return False

        return len(args) == 1 or (
            len(args) == 2 and args[1] in TwoDBaseCommand.HELP_FLAGS
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
        return not command_args or (
            len(command_args) == 1 and command_args[0] in self.HELP_FLAGS
        )

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
            title="2D Commands",
            description="Available 2D drawing utilities.",
            content=content,
        )
