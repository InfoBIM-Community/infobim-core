from __future__ import annotations

from typing import List, Optional

from infobim.ifc.adapter.class_catalog import IfcClassCatalogRepository
from infobim.project.plugin.parameter.project import ProjectIdStrategy
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class IfcElementCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="ifc_element",
        logical_component="ifc",
        description="Display one IFC element by GlobalId across Project datasets.",
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
                    "--element <element GlobalId>"
                ),
            },
            {
                "accepts": ["--element"],
                "valued": True,
                "description": "Select one IFC element by GlobalId.",
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
        element_value = IfcElementCommand._value_after(rest, "--element")
        if not element_value or element_value.startswith("--"):
            return False
        has_project_id = "--project-id" in rest
        has_project = "--project" in rest
        if has_project_id and has_project:
            return False
        project_id_value = IfcElementCommand._value_after(rest, "--project-id") if has_project_id else None
        if has_project_id and (not project_id_value or project_id_value.startswith("--")):
            return False
        project_value = IfcElementCommand._value_after(rest, "--project") if has_project else None
        if has_project and (not project_value or project_value.startswith("--")):
            return False
        return True

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args: List[str] = list(self._request.command_args)
        rest = args[1:] if (args and args[0] == "ifc") else list(args)

        element_global_id = IfcElementCommand._value_after(rest, "--element")
        if not element_global_id:
            raise CliCommandArgumentException(
                "Usage: infobim ifc [--project <selector>|--project-id <GlobalId>] "
                "--element <element GlobalId>"
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

        context.set_parameter_value("ifc_element", element_global_id)
        return True

    def run(self) -> CommandResponse:
        context = self._request.context
        project_id = str(context.get_parameter_value("project_id") or "").strip()
        project_path = str(context.get_parameter_value("project_path") or "").strip()
        element_global_id = str(context.get_parameter_value("ifc_element") or "").strip()

        try:
            payload = IfcClassCatalogRepository(project_path).get_element(
                element_global_id
            )
        except ValueError as error:
            raise CliCommandArgumentException(str(error)) from error

        if not payload.get("found"):
            raise CliCommandArgumentException(
                f"IFC element not found in Project '{project_id or project_path}': "
                f"{element_global_id}"
            )

        return CommandResponse(
            title=f"IFC {payload['class_name']} Element",
            description=(
                f"Resolved IFC element '{element_global_id}' as "
                f"'{payload['class_name']}' in Project "
                f"'{project_id or project_path}'."
            ),
            content={
                "project_id": project_id,
                "project_path": project_path,
                **payload,
            },
        )
