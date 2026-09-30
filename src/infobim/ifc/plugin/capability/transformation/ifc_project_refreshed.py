from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.project.plugin.machine.project_refresh.state import (
    ProjectRefreshProcessState,
)
from infobim.project.plugin.check.is_ifc_project_refreshed.hotfix import (
    main as refresh_ifc_project,
)


class IfcProjectRefreshedCapability(TransactionCapability):
    """
    Re-declares the IfcProject and resolves its schema-specific
    ifcOWL type after the container refresh rewrites the list of files
    the project container holds.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "ifc_project_refreshed"
        ),
        version="1.0.0",
        name="IfcProject Refreshed",
        description=(
            "Re-declare the IfcProject using the actual IFC files now "
            "present in the refreshed project container and ensure its "
            "schema-specific ifcOWL rdf:type is up to date."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "ifc", "refresh"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "The IfcProject declaration and its schema-specific "
                    "ifcOWL type are refreshed from the container's "
                    "current IFC payload."
                ),
            },
            "debug_entry": {
                "en": (
                    "Refreshing the IfcProject declaration in "
                    "payload/triple/ifc_project.ttl."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "IfcProject Refreshed"

    def description(self, lang: str = "en") -> str:
        return (
            "Re-declares the IfcProject and its schema-specific ifcOWL "
            "type after the container refresh step."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path_value: Any = context.get_parameter_value("container_path")
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise ValueError(
                "The project path is missing from the command context."
            )

        project_path: Path = Path(project_path_value).expanduser().resolve()
        exit_code: int = refresh_ifc_project(project_path=str(project_path))
        if exit_code != 0:
            raise RuntimeError(
                f"Failed to refresh the IfcProject declaration for "
                f"the project at {project_path}."
            )

        return {
            "resulting_state": ProjectRefreshProcessState.IFC_PROJECT_REFRESHED,
            "project_path": str(project_path),
        }
