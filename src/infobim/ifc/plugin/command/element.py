from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from infobim.ifc.adapter.command_arguments import IfcCommandArguments
from infobim.ifc.plugin.capability.query.element import IfcElementQueryCapability
from infobim.ifc.plugin.command.support import IfcProjectQueryCommand
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class IfcElementCommand(IfcProjectQueryCommand):
    METADATA = CliCommandMetadata(
        id="ifc_element",
        logical_component="ifc",
        description="Display one IFC element by GlobalId across Project datasets.",
        arguments=[
            {
                "accepts": ["--project-id", "--project"],
                "valued": True,
                "parameter": "project_id",
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
                "parameter": "element_global_id",
                "description": "Select one IFC element by GlobalId.",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        valued_flags: Set[str] = set(IfcCommandArguments.PROJECT_FLAGS)
        valued_flags.add("--element")
        parsed: Optional[Dict[str, Optional[str]]] = IfcCommandArguments.parse(
            args,
            valued_flags=valued_flags,
            switch_flags=set(),
        )
        return parsed is not None and "--element" in parsed

    def check(self) -> bool:
        self.require_project()
        element_global_id: str = str(
            self.context.get_parameter_value("element_global_id") or ""
        ).strip()
        if not element_global_id:
            raise CliCommandArgumentException(
                "Usage: infobim ifc [--project <selector>|--project-id <GlobalId>] "
                "--element <element GlobalId>"
            )

        return True

    def run(self) -> CommandResponse:
        context: CliContextPort = self.context
        project_id: str = str(
            context.get_parameter_value("project_id") or ""
        ).strip()
        project_path: str = str(
            context.get_parameter_value("project_path") or ""
        ).strip()
        element_global_id: str = str(
            context.get_parameter_value("element_global_id") or ""
        ).strip()

        payload: Dict[str, Any] = self.execute_capability(IfcElementQueryCapability())

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
