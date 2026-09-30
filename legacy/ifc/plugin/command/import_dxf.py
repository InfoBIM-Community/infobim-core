from pathlib import Path
from typing import ClassVar, List, Optional, Tuple

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.ifc.plugin.machine.dxf_import.machine import (
    IfcImportStateTransitionHandler,
)


class IfcImportCommand(CliCommandPort):
    """Prepare a DXF source for import as an IFC representation kind."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ifc_import",
        logical_component="ifc",
        description="Prepare a DXF source for import as an IFC representation kind.",
        arguments=[
            {
                "accepts": ["--kind"],
                "valued": True,
                "parameter": "ifc_kind",
                "description": (
                    "Target IFC representation kind, for example FootPrint, "
                    "Annotation, or Axis."
                ),
                "usage": "infobim ifc --kind <kind> --import <path/to/file.dxf>",
            },
            {
                "accepts": ["--import"],
                "valued": True,
                "parameter": "import_path",
                "description": "Path to the DXF source file.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ifc"
    KIND_FLAG: ClassVar[str] = "--kind"
    IMPORT_FLAG: ClassVar[str] = "--import"
    KIND_KEY: ClassVar[str] = "ifc_kind"
    IMPORT_PATH_KEY: ClassVar[str] = "import_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != IfcImportCommand.COMPONENT:
            return False
        return IfcImportCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request = request

    def check(self) -> bool:
        values = self._values(self._request.command_args)
        if values is None:
            return False

        kind, raw_path = values
        source_path = Path(raw_path).expanduser()
        if source_path.suffix.lower() != ".dxf":
            raise CliCommandArgumentException(
                f"IFC import currently accepts a DXF source path: {source_path}"
            )

        self._request.context.set_parameter_value(self.KIND_KEY, kind)
        self._request.context.set_parameter_value(
            self.IMPORT_PATH_KEY,
            str(source_path),
        )
        return True

    def run(self) -> CommandResponse:
        return IfcImportStateTransitionHandler(
            context=self._request.context,
        ).execute()

    @classmethod
    def _values(cls, scoped_args: List[str]) -> Optional[Tuple[str, str]]:
        remaining = list(scoped_args)
        if remaining.count(cls.KIND_FLAG) != 1:
            return None
        if remaining.count(cls.IMPORT_FLAG) != 1:
            return None

        kind_index = remaining.index(cls.KIND_FLAG)
        if kind_index + 1 >= len(remaining):
            return None
        kind = str(remaining[kind_index + 1]).strip()
        if not kind or kind.startswith("--"):
            return None
        del remaining[kind_index:kind_index + 2]

        import_index = (
            remaining.index(cls.IMPORT_FLAG)
            if cls.IMPORT_FLAG in remaining
            else -1
        )
        if import_index < 0 or import_index + 1 >= len(remaining):
            return None
        source = str(remaining[import_index + 1]).strip()
        if not source or source.startswith("--"):
            return None
        del remaining[import_index:import_index + 2]

        if remaining:
            return None

        return kind, source
