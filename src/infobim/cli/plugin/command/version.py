from typing import ClassVar, List
from importlib.metadata import version as distribution_version

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class InfoBIMVersionCommand(CliCommandPort):
    """
    Command to display the InfoBIM package version.

    InfoBIM runs on OntoBDC but is a distribution of its own, so the version
    a user asks for here is InfoBIM's, not the runtime it sits on.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="version",
        logical_component="cli",
        description="Display the version of InfoBIM.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--version",
                    "-v",
                ],
                "description": (
                    "Print the version string reported by the active "
                    "InfoBIM Python distribution installed in the current "
                    "environment."
                ),
            },
        ],
    )

    DISTRIBUTION: ClassVar[str] = "infobim"
    VERSION_FLAGS: ClassVar[List[str]] = ["--version", "-v"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the version command at the CLI routing stage.
        """
        return (
            len(args) == 1
            and args[0] in InfoBIMVersionCommand.VERSION_FLAGS
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self.accepts(self._request.command_args)

    def run(self) -> CommandResponse:
        """
        Report the version of the installed InfoBIM distribution.
        """
        return CommandResponse(
            title="InfoBIM Version",
            description="Display the InfoBIM package version.",
            content={
                "version": distribution_version(self.DISTRIBUTION),
            },
        )
