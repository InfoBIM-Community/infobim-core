from __future__ import annotations

from typing import List, Optional

from infobim.ifc.adapter.class_catalog import IfcClassCatalogRepository
from infobim.project.plugin.parameter.project import ProjectIdStrategy
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class IfcClassElementsAllCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="ifc_class_elements_all",
        logical_component="ifc",
        description="List all elements of one IFC class across Project datasets.",
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
                    "--class <class_name> --all"
                ),
            },
            {
                "accepts": ["--class"],
                "valued": True,
                "description": "Select an IFC class by local name or full class URI.",
            },
            {
                "accepts": ["--all"],
                "description": "List all elements of the selected IFC class.",
            },
        ],
    )

    @staticmethod
    def _value_after(args: List[str], flag: str) -> Optional[str]:
        try:
            idx = args.index(flag)
        except ValueError:
            return None
        if idx + 1 >= len(args):
            return None
        value = str(args[idx + 1] or "").strip()
        return value or None

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "ifc":
            return False
        rest = args[1:]
        has_class_flag = "--class" in rest
        has_all_flag = "--all" in rest
        if not (has_class_flag and has_all_flag):
            return False
        class_value = IfcClassElementsAllCommand._value_after(rest, "--class")
        if not class_value or class_value.startswith("--"):
            return False
        has_project_id = "--project-id" in rest
        has_project = "--project" in rest
        if has_project_id and has_project:
            return False
        project_id_value = IfcClassElementsAllCommand._value_after(rest, "--project-id") if has_project_id else None
        if has_project_id and (not project_id_value or project_id_value.startswith("--")):
            return False
        project_value = IfcClassElementsAllCommand._value_after(rest, "--project") if has_project else None
        if has_project and (not project_value or project_value.startswith("--")):
            return False
        return True

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args: List[str] = list(self._request.command_args)
        rest = args[1:] if (args and args[0] == "ifc") else list(args)

        if "--class" not in rest or "--all" not in rest:
            return False

        class_name = IfcClassElementsAllCommand._value_after(rest, "--class")
        if not class_name:
            raise CliCommandArgumentException(
                "Usage: infobim ifc [--project <selector>|--project-id <GlobalId>] "
                "--class <class_name> --all"
            )

        if not hasattr(self._request, "context") or self._request.context is None:
            raise CliCommandArgumentException(
                "Missing CLI context. Cannot resolve InfoBIM project."
            )

        context = self._request.context
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

        context.set_parameter_value("ifc_class", class_name)
        return True

    def run(self) -> CommandResponse:
        context = self._request.context
        project_id = str(context.get_parameter_value("project_id") or "").strip()
        project_path = str(context.get_parameter_value("project_path") or "").strip()
        class_name = str(context.get_parameter_value("ifc_class") or "").strip()

        payload = IfcClassCatalogRepository(project_path).list_elements(class_name)
        if not payload.get("class_uri"):
            raise CliCommandArgumentException(
                f"IFC class not found in Project '{project_id or project_path}': {class_name}"
            )

        return CommandResponse(
            title=f"IFC {payload['class_name']} Elements",
            description=(
                f"Found {int(payload['element_count'])} element(s) of "
                f"class '{payload['class_name']}' in Project "
                f"'{project_id or project_path}'."
            ),
            content={
                "project_id": project_id,
                "project_path": project_path,
                **payload,
            },
        )
