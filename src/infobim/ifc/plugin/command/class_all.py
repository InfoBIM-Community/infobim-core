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
                "accepts": ["--project-id"],
                "valued": True,
                "description": "Select the InfoBIM Project by IfcProject GlobalId.",
                "usage": "infobim ifc --project-id <IfcProject GlobalId> --class --all",
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
        return (
            len(args) == 5
            and args[0] == "ifc"
            and args[1] == "--project-id"
            and bool(str(args[2]).strip())
            and args[3:] == ["--class", "--all"]
        )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args = list(self._request.command_args)
        if not (
            len(args) == 4
            and args[0] == "--project-id"
            and bool(str(args[1]).strip())
            and args[2:] == ["--class", "--all"]
        ):
            return False

        self._request.context.set_parameter_value("project_id", str(args[1]).strip())
        ProjectIdStrategy().execute(self._request.context)
        project_path = str(
            self._request.context.get_parameter_value("project_path") or ""
        ).strip()
        if not project_path:
            raise CliCommandArgumentException(
                f"InfoBIM Project not found: {str(args[1]).strip()}"
            )
        return True

    def run(self) -> CommandResponse:
        project_id = str(
            self._request.context.get_parameter_value("project_id") or ""
        ).strip()
        project_path = str(
            self._request.context.get_parameter_value("project_path") or ""
        ).strip()
        payload = IfcClassCatalogRepository(project_path).list_classes()
        return CommandResponse(
            title="IFC Classes",
            description=(
                f"Found {int(payload['class_count'])} IFC class(es) and "
                f"{int(payload['element_count'])} element(s) in Project '{project_id}'."
            ),
            content={
                "project_id": project_id,
                **payload,
            },
        )
