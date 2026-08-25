from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.schedule.adapter.screen import serve
from infobim.schedule.adapter.workbook import (
    ScheduleWorkbookAdapter,
    ScheduleWorkbookError,
)


class ScheduleTaskCommand(CliCommandPort):
    """Open the local screen that records tasks into the container schedule."""

    METADATA = CliCommandMetadata(
        id="schedule_task",
        logical_component="schedule",
        description=(
            "Open a local screen to record tasks and progress into the "
            "container's schedule workbook."
        ),
        arguments=[
            # Deliberately first: the domain help and the root command table
            # render `arguments[0]` only (see infobim.cli.adapter.help), so
            # the leading entry has to be the one that names what the
            # command does, not the first option it happens to take.
            {
                "accepts": ["--task"],
                "valued": False,
                "description": (
                    "Open a local screen to record tasks and progress into "
                    "the container's schedule workbook."
                ),
                "usage": "infobim schedule --task",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "description": (
                    "Container directory to write into. Defaults to the "
                    "current directory."
                ),
                "usage": "infobim schedule --container <path>",
            },
            {
                "accepts": ["--port"],
                "valued": True,
                "description": (
                    "Port for the local screen. Defaults to any free port."
                ),
                "usage": "infobim schedule --port 8800",
            },
            {
                "accepts": ["--no-browser"],
                "valued": False,
                "description": (
                    "Print the address instead of opening a browser."
                ),
                "usage": "infobim schedule --no-browser",
            },
        ],
    )

    _VALUED_FLAGS = {"--container", "--port"}
    # `--task` is the command's own name rather than a switch: opening the
    # screen is the only thing this command does, so accepting it plain
    # costs nothing and lets `infobim schedule` alone work too.
    _FLAGS = {"--task", "--no-browser"}

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "schedule":
            return False
        return ScheduleTaskCommand._parse(args[1:]) is not None

    def check(self) -> bool:
        return self._parse(list(self._request.command_args)) is not None

    @classmethod
    def _parse(cls, arguments: List[str]) -> Optional[Dict[str, Any]]:
        """Read this command's own flags, or report that they do not fit.

        Returning ``None`` rather than raising is what lets ``accepts`` and
        ``check`` share one definition of a valid invocation: a malformed
        call must fall through to the loader so it can report an unknown
        command, not blow up mid-dispatch.
        """
        parsed: Dict[str, Any] = {
            "container": ".",
            "port": 0,
            "open_browser": True,
        }
        seen: set = set()
        index: int = 0
        while index < len(arguments):
            flag: str = arguments[index]
            if flag in cls._FLAGS:
                if flag in seen:
                    return None
                seen.add(flag)
                if flag == "--no-browser":
                    parsed["open_browser"] = False
                index += 1
                continue
            if flag not in cls._VALUED_FLAGS or flag in seen:
                return None
            if index + 1 >= len(arguments):
                return None
            value: str = arguments[index + 1]
            if value.startswith("--") or not value.strip():
                return None
            if flag == "--container":
                parsed["container"] = value
            else:
                if not value.strip().isdigit():
                    return None
                parsed["port"] = int(value)
            seen.add(flag)
            index += 2
        return parsed

    def run(self) -> CommandResponse:
        options: Optional[Dict[str, Any]] = self._parse(
            list(self._request.command_args)
        )
        if options is None:
            raise ValueError(
                "Invalid arguments for `infobim schedule`. "
                "See `infobim schedule --help`."
            )

        try:
            adapter: ScheduleWorkbookAdapter = ScheduleWorkbookAdapter(
                Path(str(options["container"]))
            )
        except ScheduleWorkbookError as error:
            raise ValueError(str(error)) from error

        server = serve(
            adapter,
            port=int(options["port"]),
            open_browser=bool(options["open_browser"]),
        )
        address: str = f"http://127.0.0.1:{server.server_port}/"

        # Printed before serve_forever blocks: the response below is only
        # rendered once the person closes the screen, and by then knowing
        # the address is no use to them.
        print(f"planilha : {adapter.workbook_path}")
        print(f"tela     : {address}   (Ctrl+C para encerrar)")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()

        return CommandResponse(
            title="Schedule Task Entry",
            description="Local task entry screen for the container schedule.",
            content={
                "workbook": str(adapter.workbook_path),
                "datapackage": str(adapter.datapackage_path),
                "sheets": dict(adapter.sheet_names),
                "address": address,
                "task_count": len(adapter.tasks()),
            },
        )
