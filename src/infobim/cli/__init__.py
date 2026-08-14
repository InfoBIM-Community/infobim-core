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
"""

import json
import sys
from functools import partial
from typing import Sequence

from ontobdc.cli.adapter.command import CliCommandRunAdapter
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.shared.adapter.loader import CommandLoader


def main(argv: Sequence[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    logger = NullLogRepository()
    json_output = "--json" in args
    args = [arg for arg in args if arg != "--json"]

    try:
        command = CliCommandRunAdapter.make(
            args,
            logger,
            loader_class=partial(CommandLoader, root_package="infobim"),
        )
    except CliCommandArgumentException as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)

    _render_response(command.run())


def _render_response(response: object) -> None:
    title = str(getattr(response, "title", "InfoBIM"))
    description = str(getattr(response, "description", ""))
    content = getattr(response, "content", None)

    print(title)
    if description:
        print(description)
    if content:
        print(json.dumps(content, ensure_ascii=False, indent=2, default=str))
