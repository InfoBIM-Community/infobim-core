from typing import List

from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse


class InfoBIMWelcomeCommand(CliCommandPort):
    """Base command shown by ``infobim`` with no arguments."""

    METADATA = CliCommandMetadata(
        id="welcome",
        logical_component="cli",
        description="Display the InfoBIM welcome banner and available commands.",
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return not args

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return not self._request.command_args

    def run(self) -> HelpCommandResponse:
        command_tree: str = CommandTreeAdapter(
            root_package="infobim",
            executable="infobim",
            excluded_command_ids=("welcome",),
        ).render()
        return HelpCommandResponse(
            title="InfoBIM Commands",
            description="Available commands and options.",
            content={
                "Usage": "infobim <command> [flags/parameters]",
                "Commands": command_tree,
            },
        )
