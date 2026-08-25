from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim.cli.adapter.help import build_domain_help_content


class ScheduleHelpCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="schedule_help",
        logical_component="schedule",
        description="Display InfoBIM Schedule command help.",
        arguments=[{"accepts": ["--help"], "valued": False}],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args == ["schedule", "--help"]

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        return list(self._request.command_args) == ["--help"]

    def run(self) -> HelpCommandResponse:
        return HelpCommandResponse(
            title="InfoBIM Schedule",
            description=(
                "Record tasks and progress into the container's IfcWorkSchedule "
                "workbook, the same one the Gantt Surface reads."
            ),
            content=build_domain_help_content("schedule"),
        )
