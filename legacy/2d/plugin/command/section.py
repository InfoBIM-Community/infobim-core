from pathlib import Path
from typing import Any, ClassVar, List, Optional, Tuple

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.drawing.plugin.machine.section.machine import (
    IfcSectionStateTransitionHandler,
)


class DxfSectionCommand(CliCommandPort, LoggerAwarePort):
    """Generate a 2D DXF section from an IFC model through the section FSM."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_section",
        logical_component="2d",
        description=(
            "Generate a 2D DXF from native IFC plan representations when "
            "available, otherwise section the 3D Body at the requested Z."
        ),
        arguments=[
            {
                "accepts": ["--section"],
                "valued": True,
                "parameter": "ifc_path",
                "description": "Path to the IFC model.",
                "usage": "infobim 2d --section <model.ifc> --z <height>",
            },
            {
                "accepts": ["--z"],
                "valued": True,
                "parameter": "section_z",
                "description": "Horizontal section elevation in metres.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "2d"
    SECTION_FLAG: ClassVar[str] = "--section"
    Z_FLAG: ClassVar[str] = "--z"
    IFC_PATH_KEY: ClassVar[str] = "ifc_path"
    SECTION_Z_KEY: ClassVar[str] = "section_z"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != DxfSectionCommand.COMPONENT:
            return False
        return DxfSectionCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Any = None

    @property
    def log_strategy(self) -> Any:
        return self._log_strategy

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        values = self._values(self._request.command_args)
        if values is None:
            return False

        raw_path, raw_z = values
        source_path = Path(raw_path).expanduser().resolve()
        if not source_path.is_file():
            raise CliCommandArgumentException(f"IFC file not found: {source_path}")
        if source_path.suffix.lower() != ".ifc":
            raise CliCommandArgumentException(f"Not an IFC file: {source_path}")

        try:
            z = float(raw_z)
        except ValueError as error:
            raise CliCommandArgumentException(
                f"Invalid section Z: {raw_z}"
            ) from error

        self._request.context.set_parameter_value(
            self.IFC_PATH_KEY, str(source_path)
        )
        self._request.context.set_parameter_value(self.SECTION_Z_KEY, z)
        return True

    def run(self) -> CommandResponse:
        return IfcSectionStateTransitionHandler(
            context=self._request.context,
            logger=self._logger,
        ).execute()

    @classmethod
    def _values(cls, scoped_args: List[str]) -> Optional[Tuple[str, str]]:
        remaining = list(scoped_args)
        if remaining.count(cls.SECTION_FLAG) != 1 or remaining.count(cls.Z_FLAG) != 1:
            return None

        section_index = remaining.index(cls.SECTION_FLAG)
        if section_index + 1 >= len(remaining):
            return None
        raw_path = str(remaining[section_index + 1]).strip()
        if not raw_path or raw_path.startswith("--"):
            return None
        del remaining[section_index:section_index + 2]

        z_index = remaining.index(cls.Z_FLAG) if cls.Z_FLAG in remaining else -1
        if z_index < 0 or z_index + 1 >= len(remaining):
            return None
        raw_z = str(remaining[z_index + 1]).strip()
        if not raw_z or raw_z.startswith("--"):
            return None
        del remaining[z_index:z_index + 2]

        if remaining:
            return None

        return raw_path, raw_z
