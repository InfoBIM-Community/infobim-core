
import sys
from typing import List
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli import _render_response as ontobdc_render_response
from infobim.cli.adapter.loader import ResponseAnsiInformationAdapterLoader
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from infobim.cli.adapter.command import CliCommandRunAdapter as InfoBIMCliCommandRunAdapter
from ontobdc.cli.adapter.logger import BaseLoggerAdapter, InLineLogger, NullLogRepository, StandardConsoleLogger


def main() -> None:
    """
    Main entry point for the InfoBIM CLI.
    
    Parses command line arguments and dispatches to the appropriate handler.
    """
    incoming_args: List[str] = _parse_incoming_args()

    try:
        render_type: str = 'rich'
        if "--json" in sys.argv:
            render_type = 'json'
        elif "--html" in sys.argv:
            render_type = 'html'

        silent: bool = "--silent" in sys.argv or "-s" in sys.argv

        logger: LogRepositoryPort = StandardConsoleLogger()
        if render_type == 'json':
            logger = NullLogRepository()
        elif render_type == 'rich':
            logger = InLineLogger()

        cli_command_run: CliCommandPort = InfoBIMCliCommandRunAdapter.make(incoming_args, logger)
        response: CommandResponse = cli_command_run.run()
        if not silent:
            _render_response(response, logger, render_type)

        sys.exit(0)

    except Exception as e:
        response: CommandResponse = ExceptionCommandResponse(
            title="InfoBIM Run",
            description="Command execution failed.",
            content={"error": str(e)},
        )
        if not silent:
            _render_response(response, logger, render_type)
        sys.exit(1)


def _parse_incoming_args() -> List[str]:
    """
    Parse command line arguments.
    """
    return [arg for arg in sys.argv[1:] if arg not in ["--json", "--rich", "--html", "--silent", "-s"]]


def _render_response(response: CommandResponse, logger: BaseLoggerAdapter, render_type: str) -> None:
    if render_type == "rich":
        _render_rich_response(response)
        return

    ontobdc_render_response(response, logger, render_type)


def _render_rich_response(response: CommandResponse) -> None:
    loader = ResponseAnsiInformationAdapterLoader()
    adapter = loader.get(response)
    print(adapter.render(response))
