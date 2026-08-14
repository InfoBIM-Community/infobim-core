"""Self-generating command-table helpers, shared by the top-level welcome
command and every domain's `--help` command.

Mirrors `ontobdc.cli.plugin.command.base.CliBaseCommand.run()`'s own dynamic
discovery exactly, just rooted at "infobim" via `CommandLoader`'s
`root_package` parameter instead of the ontobdc default -- so a new InfoBIM
command never needs a help-text update, the same way a new ontobdc command
never does.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.adapter.loader import CommandLoader

ROOT_PACKAGE = "infobim"


def discover_logical_components(logger: Optional[LogRepositoryPort] = None) -> List[str]:
    """Every InfoBIM domain that has its own `plugin/command/` folder."""
    resolved_logger = logger or NullLogRepository()
    dummy_loader = CommandLoader("", resolved_logger, root_package=ROOT_PACKAGE)
    return sorted(
        {
            pkg.split(".")[1]
            for pkg in dummy_loader._list_plugin_folder("command", root_package=ROOT_PACKAGE)
        }
    )


def build_command_table(
    components: Sequence[str],
    *,
    exclude_ids: Tuple[str, ...] = ("welcome", "help"),
    logger: Optional[LogRepositoryPort] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build the `{display_name: {id, logical_component, accepts, description}}`
    table for every discovered command across `components`, skipping the
    welcome/help commands themselves (they don't belong in their own listing).
    """
    resolved_logger = logger or NullLogRepository()
    command_table: Dict[str, Dict[str, Any]] = {}

    for component in components:
        command_classes: List[Type[CliCommandPort]] = CommandLoader(
            component, resolved_logger, root_package=ROOT_PACKAGE
        ).get_all()
        for command_class in command_classes:
            if command_class.METADATA.id in exclude_ids:
                continue
            arguments = command_class.METADATA.arguments or []
            if not arguments or not arguments[0].get("accepts"):
                continue
            main_flag = arguments[0]["accepts"][0]
            display_name = main_flag if component == "cli" else f"{component}-{main_flag.strip('-')}"
            command_table[display_name] = {
                "id": command_class.METADATA.id,
                "logical_component": component,
                "accepts": arguments[0]["accepts"],
                "description": command_class.METADATA.description,
            }

    return command_table


def build_domain_help_content(
    component: str,
    *,
    logger: Optional[LogRepositoryPort] = None,
) -> Dict[str, Dict[str, str]]:
    """Build the `{"Usage": {id: usage}, "Options": {accepts: description}}`
    shape for one domain's `--help` command, mirroring
    `ontobdc.storage.plugin.command.help.StorageHelpCommand.run()`'s own
    algorithm exactly -- pulled straight from each discovered command's own
    METADATA, so a new command's help text never needs writing by hand.
    """
    resolved_logger = logger or NullLogRepository()
    usage: Dict[str, str] = {}
    options: Dict[str, str] = {}

    for command_class in CommandLoader(component, resolved_logger, root_package=ROOT_PACKAGE).get_all():
        # Every domain's own help command's id ends in "_help" by
        # convention (project_help, context_help, ...) -- it doesn't belong
        # in its own listing.
        if command_class.METADATA.id.endswith("_help"):
            continue
        arguments = command_class.METADATA.arguments or []
        if not arguments or not arguments[0].get("accepts"):
            continue
        primary_argument = arguments[0]
        accepts_key = " | ".join(primary_argument["accepts"])
        options[accepts_key] = primary_argument.get("description", command_class.METADATA.description)
        argument_usage = primary_argument.get("usage")
        if argument_usage:
            usage[command_class.METADATA.id] = argument_usage

    return {"Usage": usage, "Options": options}
