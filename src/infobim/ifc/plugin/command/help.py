from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim.cli.adapter.help import build_domain_help_content


class IfcHelpCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="ifc_help",
        logical_component="ifc",
        description="Display InfoBIM IFC command help.",
        arguments=[{"accepts": ["--help", "-h"], "description": "Display IFC help."}],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args in (["ifc", "--help"], ["ifc", "-h"])

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        return list(self._request.command_args) in (["--help"], ["-h"])

    def run(self) -> HelpCommandResponse:
        return HelpCommandResponse(
            title="InfoBIM IFC",
            description="Inspect IFC information exposed through Project dataset facades.",
            content=build_domain_help_content("ifc"),
        )
