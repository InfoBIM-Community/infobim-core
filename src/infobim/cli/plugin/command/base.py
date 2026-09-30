from abc import abstractmethod
from typing import Any, ClassVar, Dict, List, Tuple, Type

from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CommandLoader
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, HelpCommandResponse


class InfoBIMBaseCommand(CliCommandPort, LoggerAwarePort):
    """
    Base class for InfoBIM CLI commands.

    Carries the shared infrastructure every InfoBIM command needs: the
    ``LoggerAwarePort`` contract (``set_log_strategy`` + ``log_strategy``),
    the default ``NullLogRepository`` until the runtime wires a real one in,
    the standard ``__init__`` / ``check`` shapes, and the InfoBIM-wide
    constants for command-tree rendering that leaf commands typically reuse
    when building a ``HelpCommandResponse``.

    Leaf commands MUST override ``METADATA`` and ``accepts()``; this class
    intentionally has no concrete ``accepts()`` implementation so it can
    never be picked up as a dispatch candidate by ``CliCommandRunAdapter``
    and therefore can never collide with whichever command owns the
    default/empty invocation (that role belongs to the concrete
    ``InfoBIMWelcomeCommand``, the InfoBIM analogue of ontobdc's
    ``CliBaseCommand`` at the dispatch level).
    """

    METADATA: CliCommandMetadata

    ROOT_PACKAGE: ClassVar[str] = "infobim"
    EXECUTABLE: ClassVar[str] = "infobim"
    EXCLUDED_COMMAND_IDS: ClassVar[Tuple[str, ...]] = ()
    EXECUTABLE_ALIASES: ClassVar[Tuple[str, ...]] = ("ontobdc",)

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Any = None

    @property
    def log_strategy(self) -> Any:
        return self._log_strategy

    @staticmethod
    @abstractmethod
    def accepts(args: List[str]) -> bool:
        """
        Report whether ``args`` name this concrete command.

        Subclasses MUST override. ``InfoBIMBaseCommand`` itself intentionally
        has no dispatch identity.
        """
        raise NotImplementedError(
            "InfoBIMBaseCommand.accepts() must be implemented by a concrete subclass."
        )

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        return self.__class__.accepts(self._request.command_args)

    def _render_help_tree(
        self,
        title: str,
        description: str,
        excluded_command_ids: Tuple[str, ...] = (),
    ) -> HelpCommandResponse:
        """
        Render the InfoBIM command tree as a ``HelpCommandResponse``.

        Concrete leaf commands that need to print the command inventory
        (welcome, …) delegate to this helper instead of rebuilding the
        ``CommandTreeAdapter`` call themselves every time.

        ``CommandTreeAdapter`` resolves the ``infobim`` package directory
        generically via ``CommandTreeAdapter.get_package_root_dir`` (same
        strategy ontobdc uses for its own tree), so the scan works in any
        working directory — the caller never has to ``chdir`` into the
        repository root for the tree to be populated.
        """
        excluded: Tuple[str, ...] = (
            excluded_command_ids or self.EXCLUDED_COMMAND_IDS
        )
        command_tree: str = CommandTreeAdapter(
            logger=self._logger,
            root_package=self.ROOT_PACKAGE,
            executable=self.EXECUTABLE,
            excluded_command_ids=excluded,
            executable_aliases=self.EXECUTABLE_ALIASES,
        ).render()

        return HelpCommandResponse(
            title=title,
            description=description,
            content={
                "Usage": f"{self.EXECUTABLE} <command> [flags/parameters]",
                "Commands": command_tree,
            },
        )


class CliBaseCommand(CliCommandPort, LoggerAwarePort):
    """
    Entry-point command shown when running ``infobim cli``.

    Single responsibility: list the commands registered under the
    ``cli`` logical component (bootstrap/identity commands such as
    ``version``, ``--help``, ``init``, welcome/hello, …) without
    showing other domains — the other ``<component>BaseCommand``
    classes handle listing their own components.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="cli_base",
        logical_component="cli",
        description="Base CLI component command handler.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--help",
                    "-h",
                ],
                "description": (
                    "Print the tree of commands registered under the "
                    "``cli`` logical component of InfoBIM."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "cli"
    EXECUTABLE: ClassVar[str] = "infobim"
    ROOT_PACKAGE: ClassVar[str] = "infobim"
    HELP_FLAGS: ClassVar[List[str]] = ["--help", "-h"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != CliBaseCommand.COMPONENT:
            return False

        return len(args) == 1 or (
            len(args) == 2 and args[1] in CliBaseCommand.HELP_FLAGS
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
            title="CLI Commands",
            description="Available CLI bootstrap/identity utilities.",
            content=content,
        )
