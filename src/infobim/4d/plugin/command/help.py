from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim.cli.adapter.help import build_domain_help_content


class FourDHelpCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="4d_help",
        logical_component="4d",
        description="Display InfoBIM 4D command help.",
        arguments=[{"accepts": ["--help"], "valued": False}],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args == ["4d", "--help"]

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        return list(self._request.command_args) == ["--help"]

    def run(self) -> HelpCommandResponse:
        return HelpCommandResponse(
            title="InfoBIM 4D",
            description=(
                "Record tasks and progress in the container's "
                "IfcWorkSchedule workbook and export its Gantt as PDF."
            ),
            content=build_domain_help_content("4d"),
        )
