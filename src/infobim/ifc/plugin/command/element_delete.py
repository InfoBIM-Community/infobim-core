"""CLI command requesting confirmation to delete one IFC element (stub only)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.context import CliContextPort, PromptChoiceAwarePort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor

from infobim.ifc.plugin.capability.element.delete import IfcElementDeleteCapability
from infobim.ifc.plugin.parameter.delete_confirmation import (
    DeleteConfirmationStrategy,
)


class IfcElementDeleteCommand(CliCommandPort, PromptChoiceAwarePort):
    """Request confirmation to delete one IFC element from a raw IFC file.

    Resolves the confirmation decision (``-y`` / ``--yes``, or the
    interactive ``prompt_choice`` callback injected by the InfoBIM
    entrypoint) through :class:`DeleteConfirmationStrategy`, then hands
    the already-resolved decision to :class:`IfcElementDeleteCapability`,
    which remains a stub and never modifies the IFC file.
    """

    METADATA = CliCommandMetadata(
        id="ifc_element_delete",
        logical_component="ifc",
        description=(
            "Request confirmation to delete one IFC element. Stub only -- "
            "never modifies the IFC file."
        ),
        arguments=[
            {
                "accepts": ["--file"],
                "valued": True,
                "description": "Path to the existing IFC file.",
                "usage": (
                    "infobim ifc --file <path.ifc> --global-id <GlobalId> "
                    "--delete [-y|--yes]"
                ),
            },
            {
                "accepts": ["--global-id"],
                "valued": True,
                "description": "GlobalId of the IFC element to delete.",
            },
            {
                "accepts": ["--delete"],
                "valued": False,
                "description": "Request deletion of the selected element.",
            },
            {
                "accepts": ["-y", "--yes"],
                "valued": False,
                "description": (
                    "Skip the interactive confirmation prompt and assume yes."
                ),
            },
        ],
    )

    @staticmethod
    def _value_after(args: List[str], flag: str) -> Optional[str]:
        try:
            index = args.index(flag)
        except ValueError:
            return None
        if index + 1 >= len(args):
            return None
        value = str(args[index + 1] or "").strip()
        return value or None

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "ifc":
            return False
        rest = args[1:]
        if "--delete" not in rest:
            return False
        file_value = IfcElementDeleteCommand._value_after(rest, "--file")
        if not file_value or file_value.startswith("--"):
            return False
        global_id_value = IfcElementDeleteCommand._value_after(rest, "--global-id")
        if not global_id_value or global_id_value.startswith("--"):
            return False
        return True

    def __init__(self, request: CliCommandRequest) -> None:
        self._request = request
        self._prompt_choice: Optional[Callable[..., str]] = None

    def set_prompt_choice(self, prompt_choice: Callable[..., str]) -> None:
        self._prompt_choice = prompt_choice

    def check(self) -> bool:
        args: List[str] = list(self._request.command_args)
        rest = args[1:] if (args and args[0] == "ifc") else list(args)

        ifc_path = self._value_after(rest, "--file")
        global_id = self._value_after(rest, "--global-id")
        if not ifc_path or not global_id:
            raise CliCommandArgumentException(
                "Usage: infobim ifc --file <path.ifc> --global-id <GlobalId> "
                "--delete [-y|--yes]"
            )

        context: CliContextPort = self._request.context
        context.set_parameter_value("ifc_path", ifc_path)
        context.set_parameter_value("element_global_id", global_id)
        return True

    def run(self) -> CommandResponse:
        context: CliContextPort = self._request.context

        strategy = DeleteConfirmationStrategy()
        if self._prompt_choice is not None:
            strategy.set_prompt_choice(self._prompt_choice)
        strategy.execute(context)

        result: Dict[str, Any] = CapabilityExecutor.execute(
            IfcElementDeleteCapability(), context
        )

        return CommandResponse(
            title="IFC Element Delete (stub)",
            description=(
                f"Deletion of element '{result['element_global_id']}' was "
                f"{'confirmed' if result['confirmed'] else 'cancelled'}. "
                "The IFC file was not modified (stub)."
            ),
            content=result,
        )
