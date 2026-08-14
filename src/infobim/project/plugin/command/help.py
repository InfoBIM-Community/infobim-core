from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim.cli.adapter.help import build_domain_help_content


class ProjectHelpCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="project_help",
        logical_component="project",
        description="Display InfoBIM Project command help.",
        arguments=[{"accepts": ["--help", "-h"], "description": "Display Project help."}],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args in (["project", "--help"], ["project", "-h"])

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        return list(self._request.command_args) in (["--help"], ["-h"])

    def run(self) -> HelpCommandResponse:
        return HelpCommandResponse(
            title="InfoBIM Project",
            description="Operate an InfoBIM Project as the domain-level counterpart of an OntoBDC storage container.",
            content=build_domain_help_content("project"),
        )
