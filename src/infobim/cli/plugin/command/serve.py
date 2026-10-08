from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.cli.adapter.server import InfoBIMServer
from infobim.cli.plugin.command.base import InfoBIMBaseCommand


class InfoBIMServeCommand(InfoBIMBaseCommand):
    """
    Command to run the local InfoBIM server.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="serve",
        logical_component="cli",
        description="Run the local InfoBIM server.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "serve",
                ],
                "description": (
                    "Serve InfoBIM on 127.0.0.1, port 8765, until it is "
                    "stopped. The server answers GET /ping with its status, "
                    "its name and its version."
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 1 and args[0] == "serve"

    def __init__(self, request: CliCommandRequest) -> None:
        super().__init__(request)

    def run(self) -> CommandResponse:
        server = InfoBIMServer.make()
        self._logger.log_notice(
            f"InfoBIM is serving on http://{InfoBIMServer.HOST}:{InfoBIMServer.PORT}"
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()

        return CommandResponse(
            title="Serve",
            description="The InfoBIM server was stopped.",
            content={"host": InfoBIMServer.HOST, "port": InfoBIMServer.PORT},
        )
