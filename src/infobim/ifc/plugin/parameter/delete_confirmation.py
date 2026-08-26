"""Resolve the confirmation decision for an IFC element deletion.

Follows the exact shape of ``ContainerIdStrategy``
(``ontobdc.storage.plugin.parameter.container``): a ``CliContextStrategyPort``
that inspects the real CLI ``raw_args`` first, and only falls back to an
injected ``PromptChoiceAwarePort`` callback when no explicit flag was given.
"""

from __future__ import annotations

from typing import Callable, FrozenSet, List, Optional

from ontobdc.cli.domain.port.context import (
    CliContextPort,
    CliContextStrategyPort,
    PromptChoiceAwarePort,
)
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort


class DeleteConfirmationStrategy(
    ParameterPort,
    CliContextStrategyPort,
    PromptChoiceAwarePort,
):
    """Resolve ``confirmed`` from ``-y`` / ``--yes`` or an interactive prompt.

    ``-y`` / ``--yes`` present in ``raw_args`` confirms without prompting.
    Otherwise, when a ``prompt_choice`` callback has been injected, asks a
    Yes/No question naming the target element, defaulting to No. With
    neither an explicit flag nor an injected prompt callback, the decision
    defaults to not confirmed.
    """

    METADATA = ParameterMetadata(
        id="org.infobim.ifc.plugin.parameter.delete_confirmation",
        version="1.0.0",
        name="confirmed",
        description=(
            "Resolve -y / --yes, or an interactive Yes/No prompt, into a "
            "'confirmed' context parameter consumed by the IFC element "
            "delete capability."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=bool,
    )

    _YES_FLAGS: FrozenSet[str] = frozenset({"-y", "--yes"})
    _YES_OPTION: str = "Yes"
    _NO_OPTION: str = "No"

    def __init__(self) -> None:
        self._prompt_choice: Optional[Callable[..., str]] = None

    def set_prompt_choice(self, prompt_choice: Callable[..., str]) -> None:
        self._prompt_choice = prompt_choice

    def execute(self, context: CliContextPort) -> CliContextPort:
        raw_args: List[str] = list(getattr(context, "raw_args", None) or ())
        if self._YES_FLAGS.intersection(raw_args):
            context.set_parameter_value("confirmed", True)
            return context

        if self._prompt_choice is None:
            context.set_parameter_value("confirmed", False)
            return context

        answer: str = self._prompt_choice(
            "Delete IFC Element",
            self._question(context),
            options=[self._YES_OPTION, self._NO_OPTION],
            default=self._NO_OPTION,
            language=str(getattr(context, "language", None) or "en"),
        )
        context.set_parameter_value("confirmed", answer == self._YES_OPTION)
        return context

    @staticmethod
    def _question(context: CliContextPort) -> str:
        global_id: str = str(
            context.get_parameter_value("element_global_id") or ""
        ).strip()
        if not global_id:
            return "Delete this IFC element? This cannot be undone."
        return f"Delete IFC element '{global_id}'? This cannot be undone."
