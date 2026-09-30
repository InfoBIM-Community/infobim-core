from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from infobim.project.plugin.machine.project_create.state import ProjectCreateProcessState
from infobim.project.plugin.check.is_ifc_project_ready.hotfix import (
    main as create_ifc_project,
)
from infobim.project.plugin.check.is_ifc_project_schema_ready.hotfix import (
    main as ensure_ifc_project_schema,
)


class IfcProjectReadyCapability(TransactionCapability):
    """
    Declares the IfcProject the model of a project hangs from.

    The IFC schema is encoded by the schema-specific ifcOWL namespace used by
    the IfcProject rdf:type in ``payload/triple/ifc_project.ttl``.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "ifc_project_ready"
        ),
        version="0.1.0",
        name="IfcProject Ready",
        description=(
            "Declare the single IfcProject instance with a schema-specific "
            "ifcOWL rdf:type in payload/triple/ifc_project.ttl inside the "
            "reserved InfoBIM dataset."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "ifc", "create"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "The reserved InfoBIM dataset declares the project's "
                    "IfcProject using its schema-specific ifcOWL type."
                ),
            },
            "debug_entry": {
                "en": (
                    "Declaring the IfcProject in "
                    "payload/triple/ifc_project.ttl."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "IfcProject Ready"

    def description(self, lang: str = "en") -> str:
        return (
            "Declares the IfcProject using the schema-specific ifcOWL "
            "namespace in payload/triple/ifc_project.ttl."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Declare the IfcProject and ensure its ifcOWL type carries the schema.
        """
        project_path_value: Any = context.get_parameter_value("container_path")
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise ValueError(
                "The project path is missing from the command context."
            )

        project_path: Path = Path(project_path_value).expanduser().resolve()
        exit_code: int = create_ifc_project(project_path=str(project_path))
        if exit_code != 0:
            raise RuntimeError(
                f"Failed to declare the IfcProject of the project at "
                f"{project_path}."
            )

        schema_exit_code: int = ensure_ifc_project_schema(
            project_path=str(project_path)
        )
        if schema_exit_code != 0:
            raise RuntimeError(
                f"Failed to resolve the IFC schema from the IfcProject "
                f"ifcOWL type at {project_path}."
            )

        return {
            "resulting_state": ProjectCreateProcessState.IFC_PROJECT_READY,
            "path": str(project_path),
        }
