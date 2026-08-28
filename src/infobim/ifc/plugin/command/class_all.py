from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from infobim.ifc.adapter.command_arguments import IfcCommandArguments
from infobim.ifc.plugin.capability.query.classes import IfcClassesQueryCapability
from infobim.ifc.plugin.command.support import IfcProjectQueryCommand
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class IfcClassAllCommand(IfcProjectQueryCommand):
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
        valued_flags: Set[str] = set(IfcCommandArguments.PROJECT_FLAGS)
        parsed: Optional[Dict[str, Optional[str]]] = IfcCommandArguments.parse(
            args,
            valued_flags=valued_flags,
            switch_flags={"--class", "--all"},
        )
        return (
            parsed is not None
            and "--class" in parsed
            and "--all" in parsed
        )

    def check(self) -> bool:
        self.require_project()
        return True

    def run(self) -> CommandResponse:
        context: CliContextPort = self.context
        project_id: str = str(
            context.get_parameter_value("project_id") or ""
        ).strip()
        project_path: str = str(
            context.get_parameter_value("project_path") or ""
        ).strip()
        payload: Dict[str, Any] = self.execute_capability(
            IfcClassesQueryCapability()
        )
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
