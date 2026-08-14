from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim import __version__


class InfoBIMVersionCommand(CliCommandPort):
    """Display the InfoBIM package version."""

    METADATA = CliCommandMetadata(
        id="version",
        logical_component="cli",
        description="Display the version of InfoBIM.",
        arguments=[
            {
                "accepts": ["--version", "-v"],
                "description": "Display the InfoBIM package version.",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 1 and args[0] in ("--version", "-v")

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        return self.accepts(self._request.command_args)

    def run(self) -> CommandResponse:
        return CommandResponse(
            title="InfoBIM Version",
            description="Display the InfoBIM package version.",
            content={"version": __version__},
        )
