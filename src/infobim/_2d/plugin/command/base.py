from typing import Any, ClassVar, Dict, List, Tuple, Type

from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim._2d.adapter.command import TwoDCommandLoader
from infobim.shared.adapter.config import InfoBIMConfigDataAdapter


class TwoDBaseCommand(CliCommandPort, LoggerAwarePort):
    """
    Entry-point command shown when running ``infobim 2d``.

    Single responsibility: report whether the optional 2D viewer stack
    (PySide6 + Qt DXF viewer, installed via the ``[2d]`` extra) is
    available and, when enabled, print the tree of commands registered
    under the ``2d`` logical component.

    Automatic installation of the optional 2d extra is intentionally a
    *separate* command (``TwoDEnableCommand`` in ``enable.py``) so this
    class never owns the side-effect of mutating the active Python
    environment — the SRP split between "describe/status" and
    "install/enable" mirrors the ontobdc pattern of keeping component
    base commands stateless.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_base",
        logical_component="2d",
        description="Base 2D command handler.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--help",
                    "-h",
                ],
                "description": (
                    "Print the status of the optional 2D stack and the "
                    "tree of every 2D command registered in the active "
                    "executable."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "2d"
    EXECUTABLE: ClassVar[str] = "infobim"
    ROOT_PACKAGE: ClassVar[str] = "infobim"
    HELP_FLAGS: ClassVar[List[str]] = ["--help", "-h"]
    ENABLE_FLAG: ClassVar[str] = "--enable"
    EXTRA_NAME: ClassVar[str] = "2d"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the bare ``infobim 2d`` entrypoint, optionally with
        ``--help`` / ``-h`` as the only other word.

        ``--enable`` is intentionally handled by ``TwoDEnableCommand``
        and must therefore never match here.
        """
        if not args or args[0] != TwoDBaseCommand.COMPONENT:
            return False

        if TwoDBaseCommand.ENABLE_FLAG in args:
            return False

        if len(args) == 1:
            return True

        return len(args) == 2 and args[1] in TwoDBaseCommand.HELP_FLAGS

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
        if self.ENABLE_FLAG in command_args:
            return False

        if not command_args:
            return True

        if len(command_args) == 1:
            return command_args[0] in self.HELP_FLAGS

        return False

    def run(self) -> HelpCommandResponse:
        if not InfoBIMConfigDataAdapter.is_2d_installed():
            return self._disabled_response()

        return self._enabled_response()

    def _disabled_response(self) -> HelpCommandResponse:
        installation_bullets: str = (
            f"1. python -m pip install 'infobim[{self.EXTRA_NAME}]'\n"
            f"2. {self.EXECUTABLE} {self.COMPONENT} {self.ENABLE_FLAG}"
        )

        content: Dict[str, str] = {
            "Status": "The 2D extra is not installed.",
            "Why missing": (
                "PySide6 (the Qt stack required by the interactive "
                "DXF viewer commands) is packaged as a heavy optional "
                "wheel and is never part of the base InfoBIM install."
            ),
            "To enable it": installation_bullets,
        }

        return HelpCommandResponse(
            title="2D Viewer — Disabled",
            description=(
                "The 2D stack is not installed. Install the 2d extra "
                "or run the enable command to activate it."
            ),
            content=content,
        )

    def _enabled_response(self) -> HelpCommandResponse:
        component_commands: List[Tuple[str, Type[CliCommandPort]]] = [
            (self.COMPONENT, command_class)
            for command_class in TwoDCommandLoader(self._logger).get_all()
        ]
        command_tree: str = CommandTreeAdapter(
            logger=self._logger,
            root_package=self.ROOT_PACKAGE,
            executable=self.EXECUTABLE,
            command_classes=component_commands,
        ).render()

        content: Dict[str, str] = {
            "Status": "2D viewer is installed and enabled.",
            "Usage": f"{self.EXECUTABLE} {self.COMPONENT} [flags/parameters]",
            "Commands": command_tree,
        }

        return HelpCommandResponse(
            title="2D Commands",
            description="Available 2D drawing utilities.",
            content=content,
        )
