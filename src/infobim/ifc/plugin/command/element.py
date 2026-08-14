from __future__ import annotations

from typing import List

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
                "accepts": ["--project-id"],
                "valued": True,
                "description": "Select the InfoBIM Project by IfcProject GlobalId.",
                "usage": (
                    "infobim ifc --project-id <IfcProject GlobalId> "
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
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 5
            and args[0] == "ifc"
            and args[1] == "--project-id"
            and bool(str(args[2]).strip())
            and args[3] == "--element"
            and bool(str(args[4]).strip())
        )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args = list(self._request.command_args)
        if not (
            len(args) == 4
            and args[0] == "--project-id"
            and bool(str(args[1]).strip())
            and args[2] == "--element"
            and bool(str(args[3]).strip())
        ):
            return False

        project_id = str(args[1]).strip()
        element_global_id = str(args[3]).strip()
        self._request.context.set_parameter_value("project_id", project_id)
        self._request.context.set_parameter_value("ifc_element", element_global_id)
        ProjectIdStrategy().execute(self._request.context)

        project_path = str(
            self._request.context.get_parameter_value("project_path") or ""
        ).strip()
        if not project_path:
            raise CliCommandArgumentException(
                f"InfoBIM Project not found: {project_id}"
            )
        return True

    def run(self) -> CommandResponse:
        project_id = str(
            self._request.context.get_parameter_value("project_id") or ""
        ).strip()
        project_path = str(
            self._request.context.get_parameter_value("project_path") or ""
        ).strip()
        element_global_id = str(
            self._request.context.get_parameter_value("ifc_element") or ""
        ).strip()

        try:
            payload = IfcClassCatalogRepository(project_path).get_element(
                element_global_id
            )
        except ValueError as error:
            raise CliCommandArgumentException(str(error)) from error

        if not payload.get("found"):
            raise CliCommandArgumentException(
                f"IFC element not found in Project '{project_id}': "
                f"{element_global_id}"
            )

        return CommandResponse(
            title=f"IFC {payload['class_name']} Element",
            description=(
                f"Resolved IFC element '{element_global_id}' as "
                f"'{payload['class_name']}' in Project '{project_id}'."
            ),
            content={
                "project_id": project_id,
                **payload,
            },
        )
