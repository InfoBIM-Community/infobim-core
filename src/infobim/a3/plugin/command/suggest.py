from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Set

from infobim.a3.adapter.machine import A3LlmSuggestionStateTransitionHandler
from infobim.project.plugin.parameter.project import ProjectIdStrategy
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class LlmFileSuggestionCommand(CliCommandPort):
    """Run the LLM-driven file suggestion pipeline for an InfoBIM element.

    Exact CLI shape handled by this command::

        infobim a3 \\
            --project   <project_id> \\
            --element   <element_id> \\
            --suggest   <dimension_property>

    The command is a *thin entry point*: it resolves the project via the
    shared :class:`ProjectIdStrategy`, binds the element/dimension tokens to
    the execution context, and then delegates every subsequent step to the
    ``A3LlmSuggestionStateTransitionHandler`` state machine:

    * ``container_bound`` — confirm project → container resolution
    * ``ro_crate_loaded`` — load the RO-Crate manifest
    * ``files_enumerated`` — enrich every file with RO-Crate + disk metadata
    * ``llm_evaluated`` — classify each file via Claude Haiku/Sonnet
    * ``suggestions_saved`` — persist accepted suggestions in the container
    """

    METADATA = CliCommandMetadata(
        id="a3_suggest",
        logical_component="a3",
        description=(
            "Classify every file in the project RO-Crate with Claude "
            "Haiku/Sonnet and persist accepted candidates as dimension "
            "suggestions for a target BIM element."
        ),
        arguments=[
            {
                "accepts": ["--project", "--project-id"],
                "valued": True,
                "description": (
                    "Select the target Project (IfcProject GlobalId) or "
                    "leave it implicit via the current working directory."
                ),
                "usage": (
                    "infobim a3 --project <project_id> "
                    "--element <element_id> "
                    "--suggest <dimension_property>"
                ),
            },
            {
                "accepts": ["--element"],
                "valued": True,
                "description": "Select the target Element instance by GlobalId.",
            },
            {
                "accepts": ["--suggest"],
                "valued": True,
                "description": "Declare the dimension property to suggest / evaluate.",
            },
        ],
    )

    _VALUED_FLAGS: Set[str] = {"--project", "--project-id", "--element", "--suggest"}

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "a3":
            return False
        remaining: List[str] = args[1:]
        seen: Set[str] = set()
        index = 0
        while index < len(remaining):
            flag = remaining[index]
            if flag not in LlmFileSuggestionCommand._VALUED_FLAGS or flag in seen:
                return False
            if (
                index + 1 >= len(remaining)
                or str(remaining[index + 1]).startswith("--")
            ):
                return False
            if flag == "--project" and "--project-id" in seen:
                return False
            if flag == "--project-id" and "--project" in seen:
                return False
            seen.add(flag)
            index += 2
        return bool(seen)

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        context = self._request.context
        if getattr(context, "delete_parameter", None) is not None:
            for parameter in (
                "container_id",
                "container_path",
                "target_element_id",
                "target_dimension_property",
                "a3_suggestion_state",
                "a3_ro_crate_payload",
                "a3_enriched_files",
                "a3_llm_evaluation_results",
            ):
                context.delete_parameter(parameter)

        raw_args: List[str] = list(getattr(context, "raw_args", []) or [])
        if not raw_args:
            command_args: List[str] = list(self._request.command_args)
            if "--project-id" not in command_args and "--project" not in command_args:
                explicit_project: Optional[str] = self._argument_value("--project") or self._argument_value("--project-id")
                if explicit_project:
                    raw_args = ["a3", "--project", explicit_project]
                else:
                    raw_args = ["a3"]
            else:
                raw_args = list(command_args)
        context_attributes: Any = type(context)
        if hasattr(context_attributes, "raw_args") and isinstance(
            getattr(context_attributes, "raw_args", None), property
        ):
            raw_setter = getattr(context_attributes.raw_args, "fset", None)
            if callable(raw_setter):
                try:
                    raw_setter(context, list(raw_args))
                except Exception:
                    pass
        elif hasattr(context, "set_parameter_value"):
            setter = getattr(context, "set_parameter_value")
            if callable(setter):
                try:
                    setter("raw_args", list(raw_args))
                except Exception:
                    pass

        ProjectIdStrategy().execute(context)

        project_id: Optional[str] = self._context_value("project_id")
        project_path: Optional[str] = self._context_value("project_path")
        if (
            not isinstance(project_id, str)
            or not project_id.strip()
            or not isinstance(project_path, str)
            or not project_path.strip()
            or not Path(str(project_path)).expanduser().resolve().is_dir()
        ):
            raise CliCommandArgumentException(
                "No InfoBIM Project matches the given --project selector. "
                "Run `infobim project --list` to see registered Projects."
            )

        container_path: str = str(
            Path(str(project_path)).expanduser().resolve()
        )
        context.set_parameter_value("container_id", project_id)
        context.set_parameter_value("container_path", container_path)

        element_id: Optional[str] = self._argument_value("--element")
        dimension_property: Optional[str] = self._argument_value("--suggest")
        if not isinstance(element_id, str) or not element_id.strip():
            raise CliCommandArgumentException(
                "infobim a3 requires --element <element_id>."
            )
        if not isinstance(dimension_property, str) or not dimension_property.strip():
            raise CliCommandArgumentException(
                "infobim a3 requires --suggest <dimension_property>."
            )
        context.set_parameter_value("target_element_id", element_id.strip())
        context.set_parameter_value(
            "target_dimension_property", dimension_property.strip()
        )
        return True

    def run(self) -> CommandResponse:
        return A3LlmSuggestionStateTransitionHandler(
            context=self._request.context,
        ).execute()

    def _argument_value(self, flag: str) -> Optional[str]:
        args: List[str] = list(self._request.command_args)
        if flag not in args:
            return None
        index: int = args.index(flag) + 1
        if index >= len(args):
            return None
        value: str = str(args[index]).strip()
        if not value or value.startswith("--"):
            return None
        return value

    def _context_value(self, name: str) -> Optional[str]:
        context = self._request.context
        has_parameter = getattr(context, "has_parameter", None)
        get_parameter = getattr(context, "get_parameter_value", None)
        if callable(has_parameter) and callable(get_parameter) and has_parameter(name):
            raw = get_parameter(name)
            if raw is None:
                return None
            as_str = str(raw).strip()
            return as_str or None
        return None
