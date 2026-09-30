from pathlib import Path
from typing import ClassVar, List, Optional, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from infobim.drawing.adapter.ifc_to_dxf import (
    IfcDrawingConversion,
    IfcPlumbingDxfConverter,
)


class DrawingCommand(CliCommandPort):
    """Create simplified discipline drawings from IFC models."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="drawing",
        logical_component="drawing",
        description="Create a simplified discipline drawing from an IFC model.",
        arguments=[
            {
                "accepts": ["--create"],
                "valued": True,
                "parameter": "drawing_source",
                "description": "Path to the IFC model used to create the drawing.",
                "usage": (
                    "infobim drawing --create <path/to/model.ifc> "
                    "--discipline plumbing"
                ),
            },
            {
                "accepts": ["--discipline"],
                "valued": True,
                "parameter": "discipline",
                "description": "Drawing discipline. Currently supports plumbing.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "drawing"
    CREATE_FLAG: ClassVar[str] = "--create"
    DISCIPLINE_FLAG: ClassVar[str] = "--discipline"
    PLUMBING: ClassVar[str] = "plumbing"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != DrawingCommand.COMPONENT:
            return False
        return DrawingCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        values = self._values(self._request.command_args)
        if values is None:
            return False

        source_value, discipline = values
        if discipline.lower() != self.PLUMBING:
            raise CliCommandArgumentException(
                f"Unsupported drawing discipline: {discipline}. "
                f"Supported discipline: {self.PLUMBING}."
            )

        source = Path(source_value).expanduser().resolve()
        if not source.is_file():
            raise CliCommandArgumentException(f"IFC model not found: {source}")
        if source.suffix.lower() != ".ifc":
            raise CliCommandArgumentException(
                f"Drawing source must be an IFC file: {source}"
            )

        self._request.context.set_parameter_value("drawing_source", str(source))
        self._request.context.set_parameter_value("discipline", self.PLUMBING)
        return True

    def run(self) -> CommandResponse:
        source_value = self._request.context.get_parameter_value("drawing_source")
        discipline = self._request.context.get_parameter_value("discipline")
        if not isinstance(source_value, str) or not source_value.strip():
            raise CliCommandArgumentException(
                "Required parameter is missing: drawing_source"
            )
        if str(discipline).lower() != self.PLUMBING:
            raise CliCommandArgumentException(
                "Required parameter is missing or invalid: discipline"
            )

        conversion: IfcDrawingConversion = IfcPlumbingDxfConverter.convert(
            Path(source_value)
        )
        return CommandResponse(
            title="Plumbing Drawing Created",
            description=(
                "Created a plan-view DXF from plumbing elements in the IFC model."
            ),
            content={
                "source": conversion.source,
                "discipline": conversion.discipline,
                "dxf_path": conversion.output,
                "centerlines": conversion.centerlines,
                "outlines": conversion.outlines,
                "skipped_geometry": conversion.skipped_geometry,
                "layer": IfcPlumbingDxfConverter.LAYER_NAME,
                "color": "blue",
                "linetype": "dashed",
            },
        )

    @classmethod
    def _values(cls, scoped_args: List[str]) -> Optional[Tuple[str, str]]:
        remaining = list(scoped_args)
        source = cls._extract(remaining, cls.CREATE_FLAG)
        discipline = cls._extract(remaining, cls.DISCIPLINE_FLAG)
        if source is None or discipline is None or remaining:
            return None
        return source, discipline

    @staticmethod
    def _extract(remaining: List[str], flag: str) -> Optional[str]:
        if flag not in remaining:
            return None
        index = remaining.index(flag)
        if index + 1 >= len(remaining):
            return None
        value = remaining[index + 1]
        if not value.strip():
            return None
        del remaining[index:index + 2]
        return value.strip()
