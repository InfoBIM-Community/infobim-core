from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from infobim.ifc.adapter.command_arguments import IfcCommandArguments
from infobim.ifc.plugin.capability.query.class_elements import (
    IfcClassElementsQueryCapability,
)
from infobim.ifc.plugin.command.support import IfcProjectQueryCommand
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class IfcClassElementsAllCommand(IfcProjectQueryCommand):
    METADATA = CliCommandMetadata(
        id="ifc_class_elements_all",
        logical_component="ifc",
        description="List all elements of one IFC class across Project datasets.",
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
                    "--class <class_name> --all"
                ),
            },
            {
                "accepts": ["--class"],
                "valued": True,
                "parameter": "ifc_class",
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
        valued_flags: Set[str] = set(IfcCommandArguments.PROJECT_FLAGS)
        valued_flags.add("--class")
        parsed: Optional[Dict[str, Optional[str]]] = IfcCommandArguments.parse(
            args,
            valued_flags=valued_flags,
            switch_flags={"--all"},
        )
        return parsed is not None and "--class" in parsed and "--all" in parsed

    def check(self) -> bool:
        self.require_project()
        class_name: str = str(
            self.context.get_parameter_value("ifc_class") or ""
        ).strip()
        if not class_name:
            raise CliCommandArgumentException(
                "Usage: infobim ifc [--project <selector>|--project-id <GlobalId>] "
                "--class <class_name> --all"
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
        class_name: str = str(
            context.get_parameter_value("ifc_class") or ""
        ).strip()

        payload: Dict[str, Any] = self.execute_capability(
            IfcClassElementsQueryCapability()
        )
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
