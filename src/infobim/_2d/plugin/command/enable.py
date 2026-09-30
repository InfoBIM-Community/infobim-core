from pathlib import Path
import subprocess
import sys
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim.shared.adapter.config import InfoBIMConfigDataAdapter


class TwoDEnableCommand(CliCommandPort, LoggerAwarePort):
    """
    Command responsible for installing the optional InfoBIM 2D extra.

    Single responsibility: run ``python -m pip install --upgrade
    'infobim[2d]'`` using the same Python interpreter that hosts the
    running ``infobim`` CLI. Any side-effects that mutate the active
    environment are intentionally isolated in this dedicated class,
    keeping the base command (``TwoDBaseCommand`` in ``base.py``)
    stateless and free of install side-effects.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_enable",
        logical_component="2d",
        description="Install the optional 2D viewer extra (PySide6 / Qt DXF viewer).",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--enable",
                ],
                "description": (
                    "Install the optional InfoBIM 2D extra, which "
                    "brings PySide6 and the Qt-backed interactive DXF "
                    "viewer. Equivalent to manually running "
                    "'python -m pip install --upgrade 'infobim[2d]''."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "2d"
    EXECUTABLE: ClassVar[str] = "infobim"
    ENABLE_FLAG: ClassVar[str] = "--enable"
    EXTRA_NAME: ClassVar[str] = "2d"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match exactly ``infobim 2d --enable`` (possibly with help
        flags stripped so matchers stay composable).
        """
        if not args or args[0] != TwoDEnableCommand.COMPONENT:
            return False

        if TwoDEnableCommand.ENABLE_FLAG not in args:
            return False

        remaining: List[str] = [
            arg for arg in args if arg != TwoDEnableCommand.COMPONENT
            and arg != TwoDEnableCommand.ENABLE_FLAG
        ]
        return not remaining

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
        return (
            len(command_args) == 1
            and command_args[0] == self.ENABLE_FLAG
        )

    def run(self) -> HelpCommandResponse:
        infobim_requirement: str = f"infobim[{self.EXTRA_NAME}]"
        executable: Path = Path(sys.executable)

        try:
            subprocess.run(
                [
                    str(executable),
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    infobim_requirement,
                ],
                check=True,
                stdin=None,
            )

        except (subprocess.CalledProcessError, OSError) as error:
            content: Dict[str, str] = {
                "Status": "Failed to install the 2D extra.",
                "Command executed": f"python -m pip install --upgrade '{infobim_requirement}'",
                "Error": str(error),
                "Manual fallback": (
                    "Run the command above in a terminal, making "
                    "sure the same Python interpreter used by "
                    f"'{self.EXECUTABLE}' is active (currently "
                    f"{executable})."
                ),
            }

            return HelpCommandResponse(
                title="2D Viewer — Enable failed",
                description=(
                    "The automatic install of the 2d extra failed. "
                    "See the error below and run the manual command."
                ),
                content=content,
            )

        if not InfoBIMConfigDataAdapter.is_2d_installed():
            return HelpCommandResponse(
                title="2D Viewer — Still unavailable",
                description=(
                    "pip reported success but the 2d extra still "
                    "cannot be imported; restart the interpreter or "
                    "re-run the install command."
                ),
                content={
                    "Status": "Install succeeded but probe returned False.",
                    "Python interpreter": str(executable),
                },
            )

        return HelpCommandResponse(
            title="2D Viewer — Enabled",
            description=(
                "The optional 2D viewer extra is now installed and "
                "available. Run ``infobim 2d`` to see the commands."
            ),
            content={
                "Status": "2D viewer is installed and enabled.",
                "Installed via": str(executable),
                "Next step": f"{self.EXECUTABLE} 2d",
            },
        )
