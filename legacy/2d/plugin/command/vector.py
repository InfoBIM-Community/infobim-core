from typing import Any, Dict, List, Tuple, ClassVar, Optional
from pathlib import Path
from importlib import import_module

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from infobim.context.adapter.taxonomy import (
    CONTAINER_PATH_KEY, DXF_PATH_KEY, PARAMETER_KEY, MACHINE_PACKAGE,
)
from infobim.context.adapter.execution_container import ExecutionContainer

DxfVectorStateTransitionHandler: Any = import_module(
    MACHINE_PACKAGE + ".machine"
).DxfVectorStateTransitionHandler


class ElementCreationFromDxfVectorCommand(CliCommandPort, LoggerAwarePort):
    """Draw connected straight segments over a DXF and return their coordinates."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="two_d_vector",
        logical_component="2d",
        description=(
            "Draw straight segments between successive clicks over a DXF view "
            "and return the captured modelspace coordinates."
        ),
        interactive=True,
        arguments=[
            {
                "accepts": ["--vector"],
                "valued": True,
                "parameter": DXF_PATH_KEY,
                "description": "Path to the DXF used as the drawing background.",
                "usage": "infobim 2d --vector <path/to/file.dxf> [--kind <kind>] [--z <value>]",
            },
            {
                "accepts": ["--kind"],
                "valued": True,
                "parameter": PARAMETER_KEY,
                "description": "Ontology kind name or concept URI, resolved by KindStrategy.",
            },
            {
                "accepts": ["--x"],
                "valued": True,
                "parameter": "x",
                "description": "Constant X coordinate of the work plane. Not implemented yet.",
            },
            {
                "accepts": ["--y"],
                "valued": True,
                "parameter": "y",
                "description": "Constant Y coordinate of the work plane. Not implemented yet.",
            },
            {
                "accepts": ["--z"],
                "valued": True,
                "parameter": "z",
                "description": "Constant Z coordinate of the work plane.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "2d"
    FLAG: ClassVar[str] = "--vector"

    KIND_FLAG: ClassVar[str] = "--kind"

    WORK_PLANE_FLAGS: ClassVar[Dict[str, str]] = {
        "--x": "x", "--y": "y", "--z": "z",
    }

    @classmethod
    def accepts(cls, args: List[str]) -> bool:
        return bool(
            args
            and args[0] == cls.COMPONENT
            and cls._values(args[1:]) is not None
        )

    @classmethod
    def _values(
        cls, args: List[str]
    ) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
        if len(args) not in (2, 4, 6):
            return None
        source: Optional[str] = None
        kind: Optional[str] = None
        axis: Optional[str] = None
        index: int
        for index in range(0, len(args), 2):
            flag: str = args[index]
            value: str = args[index + 1].strip()
            if not value or value.startswith("--"):
                return None
            if flag == cls.FLAG and source is None:
                source = value
            elif flag == cls.KIND_FLAG and kind is None:
                kind = value
            elif flag in cls.WORK_PLANE_FLAGS and axis is None:
                axis = cls.WORK_PLANE_FLAGS[flag]
            else:
                return None
        if source is None:
            return None
        return source, kind, axis

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
        values: Optional[Tuple[str, Optional[str], Optional[str]]] = self._values(
            self._request.command_args
        )
        if values is None:
            return False

        source_path: Path = Path(values[0]).expanduser().resolve()
        if not source_path.is_file():
            raise CliCommandArgumentException(f"DXF file not found: {source_path}")
        if source_path.suffix.lower() != ".dxf":
            raise CliCommandArgumentException(f"Not a DXF file: {source_path}")

        container: Path = ExecutionContainer.locate(Path.cwd())
        if not source_path.is_relative_to(container):
            raise CliCommandArgumentException(f"DXF source is outside the execution container: {source_path}")
        self._request.context.set_parameter_value(CONTAINER_PATH_KEY, str(container))
        self._request.context.set_parameter_value(DXF_PATH_KEY, str(source_path))
        return True

    def run(self) -> CommandResponse:
        return DxfVectorStateTransitionHandler(
            context=self._request.context,
            logger=self._logger,
        ).execute()
