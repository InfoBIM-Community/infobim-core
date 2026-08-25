from __future__ import annotations

from typing import List

from infobim.ifc.adapter.class_catalog import IfcClassCatalogRepository
from infobim.project.plugin.parameter.project import ProjectIdStrategy
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class IfcClassAllCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="ifc_class_all",
        logical_component="ifc",
        description=(
            "Scan Project dataset facades and list deduplicated IFC classes "
            "with their element counts."
        ),
        arguments=[
            {
                "accepts": ["--project-id", "--project"],
                "description": (
                    "Select the InfoBIM Project by IfcProject GlobalId "
                    "(--project-id), project selector / container id / path "
                    "(--project), or omit both to resolve the project from "
                    "the current working directory. Owned by the canonical "
                    "ProjectIdStrategy parameter pipeline."
                ),
                "usage": (
                    "infobim ifc [--project-id <GlobalId>|--project <selector>] "
                    "--class --all"
                ),
            },
            {
                "accepts": ["--class"],
                "description": "Operate on IFC classes.",
            },
            {
                "accepts": ["--all"],
                "description": "List all IFC classes found in Project dataset facades.",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "ifc":
            return False
        rest = args[1:]
        has_class = "--class" in rest
        has_all = "--all" in rest
        if not (has_class and has_all):
            return False
        # Disambiguate against IfcClassElementsAllCommand, which also uses
        # --class and --all but requires --class to have a value token right
        # after it. class-all has NO value for --class.
        try:
            class_idx = rest.index("--class")
        except ValueError:
            return False
        class_has_value = (class_idx + 1 < len(rest)) and (
            not str(rest[class_idx + 1]).startswith("--")
            and rest[class_idx + 1] != "--all"
        )
        if class_has_value:
            return False
        has_project_id = "--project-id" in rest
        has_project = "--project" in rest
        if has_project_id and has_project:
            return False
        try:
            if has_project_id:
                pid_idx = rest.index("--project-id")
                pid_value_ok = (pid_idx + 1 < len(rest)) and (
                    not str(rest[pid_idx + 1]).startswith("--")
                )
                if not pid_value_ok:
                    return False
            if has_project:
                p_idx = rest.index("--project")
                p_value_ok = (p_idx + 1 < len(rest)) and (
                    not str(rest[p_idx + 1]).startswith("--")
                )
                if not p_value_ok:
                    return False
        except ValueError:
            return False
        return True

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args: List[str] = list(self._request.command_args)
        rest = args[1:] if (args and args[0] == "ifc") else list(args)

        if "--class" not in rest or "--all" not in rest:
            return False

        if not hasattr(self._request, "context") or self._request.context is None:
            raise CliCommandArgumentException(
                "Missing CLI context. Cannot resolve InfoBIM project."
            )

        context = self._request.context
        # Expose raw_args so ProjectIdStrategy can consume the same argv the
        # CLI pipeline uses for --project / --project-id resolution. This
        # harmonises `infobim ifc ...` with every other InfoBIM command that
        # routes through ProjectIdStrategy for project selectors.
        if not hasattr(context, "raw_args") or getattr(context, "raw_args", None) is None:
            try:
                setattr(context, "raw_args", list(rest))
            except Exception:
                pass

        ProjectIdStrategy().execute(context)

        project_path = str(context.get_parameter_value("project_path") or "").strip()
        if not project_path:
            raise CliCommandArgumentException(
                "Could not resolve InfoBIM Project. Pass --project-id <GlobalId> "
                "or --project <selector>, or run this command inside an InfoBIM "
                "Project / OntoBDC container directory."
            )
        return True

    def run(self) -> CommandResponse:
        context = self._request.context
        project_id = str(context.get_parameter_value("project_id") or "").strip()
        project_path = str(context.get_parameter_value("project_path") or "").strip()
        payload = IfcClassCatalogRepository(project_path).list_classes()
        return CommandResponse(
            title="IFC Classes",
            description=(
                f"Found {int(payload['class_count'])} IFC class(es) and "
                f"{int(payload['element_count'])} element(s) in Project "
                f"'{project_id or project_path}'."
            ),
            content={
                "project_id": project_id,
                "project_path": project_path,
                **payload,
            },
        )
