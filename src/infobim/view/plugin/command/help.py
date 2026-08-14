from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim.cli.adapter.help import build_domain_help_content


class ViewHelpCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="view_help",
        logical_component="view",
        description="Display InfoBIM View command help.",
        arguments=[{"accepts": ["--help"], "valued": False}],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args == ["view", "--help"]

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        return list(self._request.command_args) == ["--help"]

    def run(self) -> HelpCommandResponse:
        return HelpCommandResponse(
            title="InfoBIM View",
            description=(
                "Present an InfoBIM Project as its IfcProject and one "
                "navigable distributed IFC Model domain."
            ),
            content=build_domain_help_content("view"),
        )
