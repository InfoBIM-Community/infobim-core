from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from infobim.project.domain.model.contract import ProjectContract
from infobim.project.plugin.machine.project_create.state import ProjectCreateProcessState
from infobim.project.plugin.check.is_project_dataset_ready.hotfix import (
    main as create_project_dataset,
)


class ProjectDatasetReadyCapability(TransactionCapability):
    """
    Puts the reserved dataset an InfoBIM project is recognised by in place.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "project_dataset_ready"
        ),
        version="1.0.0",
        name="Project Dataset Ready",
        description=(
            "Ensure the reserved InfoBIM dataset exists inside the project "
            "container and is indexed by it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "dataset", "create"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "The reserved InfoBIM dataset is in place and indexed by "
                    "the project container."
                ),
            },
            "debug_entry": {
                "en": (
                    "Creating the reserved InfoBIM dataset and indexing it "
                    "into the project container."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Project Dataset Ready"

    def description(self, lang: str = "en") -> str:
        return (
            "Creates the reserved InfoBIM dataset inside the project "
            "container and indexes it."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Create the reserved dataset and index it in the project container.
        """
        project_path_value: Any = context.get_parameter_value("container_path")
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise ValueError(
                "The project path is missing from the command context."
            )

        project_path: Path = Path(project_path_value).expanduser().resolve()
        exit_code: int = create_project_dataset(
            project_path=str(project_path),
            root_path=str(context.root_path),
        )
        if exit_code != 0:
            raise RuntimeError(
                f"Failed to create the reserved InfoBIM dataset in the "
                f"project at {project_path}."
            )

        dataset_path: Path = project_path / ProjectContract.DATASET_NAME

        return {
            "resulting_state": ProjectCreateProcessState.PROJECT_DATASET_READY,
            "dataset_path": str(dataset_path),
            "exists": dataset_path.is_dir(),
        }
