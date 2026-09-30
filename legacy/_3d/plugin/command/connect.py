from typing import List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from ...adapter.terminal_server import TerminalConnection


class ThreeDConnectCommand(CliCommandPort):
    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="three_d_connect",
        logical_component="3d",
        description="Start the local SSE connection for the 3D terminal panel.",
        arguments=[],
    )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args == ["3d", "connect"]

    def check(self) -> bool:
        return self._request.command_args == ["connect"]

    def run(self) -> CommandResponse:
        language: str | None = self._request.context.language
        TerminalConnection.serve(language)
        return CommandResponse(
            title="InfoBIM 3D",
            description=(
                "Servidor SSE encerrado."
                if language is not None and language.lower().startswith("pt")
                else "SSE server stopped."
            ),
            content={"endpoint": "http://127.0.0.1:8765/events"},
        )
