from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.handler import StateTransitionHandlerPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.plugin.machine.init.machine import (
    CliInitStateTransitionHandler,
)

from infobim.cli.plugin.command.base import InfoBIMBaseCommand
from infobim.cli.plugin.machine.init.machine import (
    InfoBIMInitStateTransitionHandler,
)


class CliInitCommand(InfoBIMBaseCommand):
    """
    Command to initialize InfoBIM in a project.

    An InfoBIM project is an OntoBDC project, so OntoBDC's own init runs
    first; InfoBIM's init is handed to it as the handler to run once OntoBDC
    has genuinely finished, and neither machine knows the other's states.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="init",
        logical_component="cli",
        description="Initialize OntoBDC and InfoBIM in the current directory.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "init",
                ],
                "description": (
                    "Initialize the current working directory as an OntoBDC "
                    "project, then put in it what InfoBIM adds: on Windows, "
                    "the InfoBIM-Serve.lnk shortcut that starts infobim "
                    "serve from the project folder."
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 1 and args[0] == "init"

    def run(self) -> CommandResponse:
        infobim_handler: StateTransitionHandlerPort = InfoBIMInitStateTransitionHandler(
            context=self._request.context,
            logger=self._logger,
        )
        return CliInitStateTransitionHandler(
            context=self._request.context,
            logger=self._logger,
            next_handler=infobim_handler,
        ).execute()
