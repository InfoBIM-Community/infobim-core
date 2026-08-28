"""CLI entry point for the InfoBIM 4D Gantt PDF capability."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor

from ..capability.transformation.gantt_pdf import FourDGanttPdfCapability


class FourDGanttPdfCommand(CliCommandPort):
    """Generate a PDF from the schedule workbook mapped by a container."""

    METADATA = CliCommandMetadata(
        id="4d_gantt_pdf",
        logical_component="4d",
        description="Generate a paginated PDF of the container's 4D Gantt.",
        arguments=[
            {
                "accepts": ["--pdf"],
                "valued": False,
                "description": "Generate a paginated 4D Gantt PDF.",
                "usage": (
                    "infobim 4d --pdf [--container <path>] "
                    "[--out <file.pdf>]"
                ),
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "description": (
                    "Container directory. Defaults to the current directory."
                ),
            },
            {
                "accepts": ["--out", "-o"],
                "valued": True,
                "description": (
                    "Output path. Defaults beside the mapped workbook."
                ),
            },
        ],
    )

    _VALUED_FLAGS = {"--container", "--out", "-o"}

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    @classmethod
    def _parse(cls, arguments: List[str]) -> Optional[Dict[str, str]]:
        if "--pdf" not in arguments or arguments.count("--pdf") != 1:
            return None
        parsed: Dict[str, str] = {"container": ".", "out": ""}
        seen: set[str] = {"--pdf"}
        index: int = 0
        while index < len(arguments):
            flag: str = arguments[index]
            if flag == "--pdf":
                index += 1
                continue
            canonical: str = "--out" if flag == "-o" else flag
            if flag not in cls._VALUED_FLAGS or canonical in seen:
                return None
            if index + 1 >= len(arguments):
                return None
            value: str = str(arguments[index + 1] or "").strip()
            if not value or value.startswith("--"):
                return None
            parsed["container" if flag == "--container" else "out"] = value
            seen.add(canonical)
            index += 2
        return parsed

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return bool(
            args
            and args[0] == "4d"
            and FourDGanttPdfCommand._parse(args[1:]) is not None
        )

    def check(self) -> bool:
        parsed = self._parse(list(self._request.command_args))
        if parsed is None:
            raise CliCommandArgumentException(
                "Usage: infobim 4d --pdf [--container <path>] "
                "[--out <file.pdf>]"
            )
        context = self._request.context
        context.set_parameter_value("container_path", parsed["container"])
        context.set_parameter_value("pdf_path", parsed["out"])
        return True

    def run(self) -> CommandResponse:
        result: Dict[str, Any] = CapabilityExecutor.execute(
            FourDGanttPdfCapability(), self._request.context
        )
        return CommandResponse(
            title="4D Gantt PDF",
            description=f"Generated {result['pdf_path']}",
            content=result,
        )
