from __future__ import annotations

from typing import List

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
                "accepts": ["--project-id"],
                "valued": True,
                "description": "Select the InfoBIM Project by IfcProject GlobalId.",
                "usage": (
                    "infobim ifc --project-id <IfcProject GlobalId> "
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
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 6
            and args[0] == "ifc"
            and args[1] == "--project-id"
            and bool(str(args[2]).strip())
            and args[3] == "--class"
            and bool(str(args[4]).strip())
            and args[5] == "--all"
        )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args = list(self._request.command_args)
        if not (
            len(args) == 5
            and args[0] == "--project-id"
            and bool(str(args[1]).strip())
            and args[2] == "--class"
            and bool(str(args[3]).strip())
            and args[4] == "--all"
        ):
            return False

        project_id = str(args[1]).strip()
        class_name = str(args[3]).strip()
        self._request.context.set_parameter_value("project_id", project_id)
        self._request.context.set_parameter_value("ifc_class", class_name)
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
        class_name = str(
            self._request.context.get_parameter_value("ifc_class") or ""
        ).strip()

        payload = IfcClassCatalogRepository(project_path).list_elements(class_name)
        if not payload.get("class_uri"):
            raise CliCommandArgumentException(
                f"IFC class not found in Project '{project_id}': {class_name}"
            )

        return CommandResponse(
            title=f"IFC {payload['class_name']} Elements",
            description=(
                f"Found {int(payload['element_count'])} element(s) of "
                f"class '{payload['class_name']}' in Project '{project_id}'."
            ),
            content={
                "project_id": project_id,
                **payload,
            },
        )
