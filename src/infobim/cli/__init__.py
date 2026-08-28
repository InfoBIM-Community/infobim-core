"""InfoBIM v0.5 command-line shell.

Dispatch is declarative, not hardcoded: every InfoBIM command is a
`CliCommandPort` discovered under `infobim/<domain>/plugin/command/*.py`,
the exact same convention (and the exact same resolution machinery --
`CliCommandRunAdapter.make()`) OntoBDC's own CLI uses for itself. This file
only tells that machinery to look inside the `infobim` package instead of
`ontobdc` (via `CommandLoader`'s `root_package` parameter) -- it no longer
knows the names of InfoBIM's own domains or commands at all. A new command
just needs to exist as a properly declared `CliCommandPort`; nothing here
ever needs to change again.

Rendering reuses OntoBDC's terminal rendering pipeline wholesale
(``ResponseWidgetAdapterLoader``, ``TerminalSurfaceRenderer``, and the
markdown widget-to-markdown dispatcher) instead of the legacy
``TerminalSurface`` class (removed during the Aggressive Cleanup C pass) --
every InfoBIM command already returns one of OntoBDC's own
``CommandResponse`` types, so OntoBDC's registered widget adapters already
know how to decompose them. Only the logo/banner is InfoBIM's own
(``infobim.cli.adapter.logo.InfoBIMLogoComponent``).
"""

import subprocess
import sys
from functools import partial
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ontobdc.cli import CliParameterValidationOrchestrator
from ontobdc.cli.adapter.command import CliCommandRunAdapter
from ontobdc.cli.adapter.loader import ResponseWidgetAdapterLoader
from ontobdc.cli.adapter.logger import InLineLogger, NullLogRepository
from ontobdc.cli.adapter.terminal import prompt_choice
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.logger import LogLevel, LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.context import CliContextPort, PromptChoiceAwarePort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.shared.adapter.loader import CommandLoader, ParameterLoader
from ontobdc.shared.domain.port.component import TerminalTileRenderable
from ontobdc.shared.facade.adapter.logger import (
    clear_active_log_repository,
    set_active_log_repository,
)

from infobim.cli.adapter.logo import InfoBIMLogoComponent


class _InfoBIMOperationTile(TerminalTileRenderable):
    """A one-line brand tile injected into the shared renderer's ``OperationRegion``.

    Implements the terminal-tile contract so InfoBIM can plug its own compact
    logo into the shared ``TerminalSurfaceRenderer`` frame without having to
    depend on the legacy ``TerminalSurface`` class or re-implement the frame
    assembly / cutout drawing.  Produces the exact same visual the ``InfoBIMLogoComponent.
    render_compact`` output previously printed *outside* the frame in the previous
    (broken) legacy integration; now it opens a cutout in the top border *inside* the
    outer frame, exactly like the default builtin OntoBDC logo tile.
    """

    def render(
        self,
        *,
        columns: int,
        rows: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        return InfoBIMLogoComponent().render_compact()


def main(argv: Sequence[str] | None = None) -> None:
    incoming_args: List[str] = _parse_incoming_args(argv)

    logger: Optional[LogRepositoryPort] = None
    try:
        render_type: str = "rich"
        if "--json" in sys.argv:
            render_type = "json"
        elif "--html" in sys.argv:
            render_type = "html"

        silent: bool = "--silent" in sys.argv or "-s" in sys.argv

        logger = InLineLogger()
        if render_type == "json":
            logger = NullLogRepository()

        resolved_log_level: Optional[LogLevel]
        sanitized_incoming_args: List[str]
        resolved_log_level, sanitized_incoming_args = _consume_global_log_level(
            incoming_args
        )

        # Apply an explicit threshold before exposing the logger through the
        # global broker. When --log-level is omitted, the repository keeps
        # LogLevelPolicy.DEFAULT (NOTICE).
        if resolved_log_level is not None:
            _ = LogStrategyConfig(
                log_level=resolved_log_level,
                log_repository=logger,
            )

        set_active_log_repository(logger)

        try:
            command: CliCommandPort = CliCommandRunAdapter.make(
                sanitized_incoming_args,
                logger,
                loader_class=partial(CommandLoader, root_package="infobim"),
                defer_check=True,
            )
        except CliCommandArgumentException as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(2)

        if resolved_log_level is not None:
            request: Optional[Any] = getattr(command, "_request", None)
            context: Optional[CliContextPort] = getattr(request, "context", None)
            if context is not None:
                context.set_parameter_value("log_level", resolved_log_level)

        parameter_loader: ParameterLoader = ParameterLoader(
            logger=logger,
            root_packages=("ontobdc", "infobim"),
        )
        parameter_validator: CliParameterValidationOrchestrator = (
            CliParameterValidationOrchestrator()
        )
        parameter_validator.check(
            command,
            sanitized_incoming_args,
            logger,
            parameter_loader,
        )

        if isinstance(command, LoggerAwarePort):
            log_strategy_kwargs: Dict[str, Any] = {"log_repository": logger}
            if resolved_log_level is not None:
                log_strategy_kwargs["log_level"] = resolved_log_level
            log_strategy = LogStrategyConfig(**log_strategy_kwargs)
            command.set_log_strategy(log_strategy)

        if isinstance(command, PromptChoiceAwarePort):
            command.set_prompt_choice(prompt_choice)

        response: CommandResponse = command.run()
        if not silent:
            _render_response(response, json_output=render_type == "json")

        sys.exit(0)

    except Exception as error:
        try:
            safe_render_type: str = render_type
        except NameError:
            safe_render_type = "rich"
        try:
            safe_silent: bool = silent
        except NameError:
            safe_silent = False
        safe_logger: LogRepositoryPort = (
            logger if logger is not None else NullLogRepository()
        )
        response = ExceptionCommandResponse(
            title="Run",
            description="Command execution failed.",
            content={"error": str(error)},
        )
        if not safe_silent:
            _render_response(response, safe_render_type == "json")
        raise SystemExit(1)
    finally:
        # Always release the broker reference -- prevents stale logger
        # reuse when this entry point is called more than once inside a
        # single process (e.g. the test harness).
        clear_active_log_repository()


def _parse_incoming_args(argv: Sequence[str] | None = None) -> List[str]:
    """Strip render-style and silence flags from the argument vector.

    These tokens are consumed at the CLI layer so they never reach the
    ``CliCommandRunAdapter`` routing stage.
    """
    raw: List[str] = list(sys.argv[1:] if argv is None else argv)
    return [
        arg
        for arg in raw
        if arg not in ["--json", "--rich", "--html", "--silent", "-s"]
    ]


def _consume_global_log_level(
    args: List[str],
) -> Tuple[Optional[LogLevel], List[str]]:
    """Consume every ``--log-level`` flag and its value from *args*.

    Reuses the stateless ``LogLevelStrategy`` helpers from the shared
    OntoBDC parameter plugin so parsing / normalisation / validation are
    always identical between ``infobim`` and ``ontobdc``.
    """
    from ontobdc.cli.plugin.parameter.log_level import (
        LogLevelStrategy as _LLS,
    )

    raw_level, sanitized_args = _LLS._consume(list(args))
    resolved_level: Optional[LogLevel] = None
    if raw_level is not None:
        resolved_level = _LLS._resolve(raw_level)
    return resolved_level, sanitized_args


def _render_response(
    response: CommandResponse,
    json_output: bool,
) -> None:
    """Render a command response onto the terminal.

    A one-time logo banner is printed above the response; the response is
    decomposed into Widgets via the shared ``ResponseWidgetAdapterLoader``
    pipeline, converted to a markdown representation through the shared
    ``_response_to_markdown`` dispatcher, then laid out and framed through
    OntoBDC's ``TerminalSurfaceRenderer`` (the "Aggressive Cleanup C"
    terminal stack that replaced the legacy ``TerminalSurface`` class).
    ``--json`` bypasses Widget rendering entirely and prints the response's
    own JSON representation.
    """
    if json_output:
        _clear_terminal()
        print(response)
        return

    # Local imports to avoid the well-known top-level circular import chain
    # between cli/__init__.py and the legacy surface stack (see OntoBDC's
    # own _render_rich_response for details).  These imports are entirely
    # safe here because we are already deep inside CLI execution.
    from ontobdc.cli.adapter.loader import ResponseWidgetAdapterLoader as _RWAL
    from ontobdc.view.adapter.terminal.surface_renderer import (
        TerminalSurfaceRenderer as _TSR,
    )
    from ontobdc.view.component.widget.python import TextWidget as _TW
    from ontobdc.cli import __dict__ as _ontobdc_cli_exports  # noqa: E402  (keep local)

    # Pull the shared markdown dispatcher from OntoBDC's CLI module so the
    # GraphWidget / TableWidget / KeyValueWidget / CodeBlockWidget branch
    # logic stays in one place (the exact same one used by `ontobdc` itself).
    _response_to_markdown: Any = _ontobdc_cli_exports["_response_to_markdown"]
    _ux_theme_for: Any = _ontobdc_cli_exports["_ux_theme_for"]

    body_markdown: str = _response_to_markdown(
        response,
        response_loader_cls=_RWAL,
        text_widget_cls=_TW,
        widget_protocol=None,
    )

    theme: str = _ux_theme_for(response)
    output: str = _TSR.with_content_surface(
        body_markdown=body_markdown,
        theme=theme,
        operation_tile=_InfoBIMOperationTile(),
    )

    # Body already has the InfoBIM logo cutout at the top (operation_tile
    # override).  No need to print a second banner outside the frame -- that
    # was the legacy TerminalSurface integration that produced two logos.
    if output.strip():
        print(output, end="" if output.endswith("\n") else "\n")


def _clear_terminal() -> None:
    subprocess.run(["clear"], check=False)
