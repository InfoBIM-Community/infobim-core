from pathlib import Path
from typing import Any, ClassVar, List

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.drawing.plugin.machine.line.machine import (
    DxfLineStateTransitionHandler,
)


class DxfLineCommand(CliCommandPort, LoggerAwarePort):
    """Draw a freehand line over a DXF and return its modelspace trace."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_line",
        logical_component="2d",
        description=(
            "Draw a freehand line over a DXF view and return the captured "
            "modelspace coordinates."
        ),
        interactive=True,
        arguments=[
            {
                "accepts": ["--line"],
                "valued": True,
                "parameter": "dxf_path",
                "description": "Path to the DXF used as the drawing background.",
                "usage": "infobim 2d --line <path/to/file.dxf>",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "2d"
    FLAG: ClassVar[str] = "--line"
    DXF_PATH_KEY: ClassVar[str] = "dxf_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 3
            and args[0] == DxfLineCommand.COMPONENT
            and args[1] == DxfLineCommand.FLAG
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
        command_args: List[str] = self._request.command_args
        if not (
            len(command_args) == 2
            and command_args[0] == self.FLAG
            and bool(str(command_args[1]).strip())
        ):
            return False

        source_path = Path(command_args[1]).expanduser().resolve()
        if not source_path.is_file():
            raise CliCommandArgumentException(f"DXF file not found: {source_path}")
        if source_path.suffix.lower() != ".dxf":
            raise CliCommandArgumentException(f"Not a DXF file: {source_path}")

        self._request.context.set_parameter_value(
            self.DXF_PATH_KEY,
            str(source_path),
        )
        return True

    def run(self) -> CommandResponse:
        return DxfLineStateTransitionHandler(
            context=self._request.context,
            logger=self._logger,
        ).execute()
