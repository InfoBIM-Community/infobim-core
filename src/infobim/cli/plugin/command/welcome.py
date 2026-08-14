from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse

from infobim import __version__
from infobim.cli.adapter.help import build_command_table, discover_logical_components


class InfoBIMWelcomeCommand(CliCommandPort):
    """Bare `infobim` entry point: welcome banner plus every discovered command."""

    METADATA = CliCommandMetadata(
        id="welcome",
        logical_component="cli",
        description="Display the InfoBIM welcome banner and available commands.",
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return not args

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        return not self._request.command_args

    def run(self) -> HelpCommandResponse:
        components = discover_logical_components()
        return HelpCommandResponse(
            title="InfoBIM",
            description=(
                "BIM/OpenBIM domain layer built on OntoBDC.\n"
                f"Version: {__version__}"
            ),
            content={
                "Usage": ["infobim <command> [flags/parameters]"],
                "Commands": build_command_table(components),
            },
        )
