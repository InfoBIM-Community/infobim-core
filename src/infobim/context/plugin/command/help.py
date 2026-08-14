from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim.cli.adapter.help import build_domain_help_content


class InfoBIMContextHelpCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="context_help",
        logical_component="context",
        description="Display InfoBIM Context command help.",
        arguments=[{"accepts": ["--help", "-h"], "description": "Display Context help."}],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args in (["context", "--help"], ["context", "-h"])

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        return list(self._request.command_args) in (["--help"], ["-h"])

    def run(self) -> HelpCommandResponse:
        return HelpCommandResponse(
            title="InfoBIM Context",
            description="Operate OntoBDC context entities through InfoBIM Projects.",
            content=build_domain_help_content("context"),
        )
