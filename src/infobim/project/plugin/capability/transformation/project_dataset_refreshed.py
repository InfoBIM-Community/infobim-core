from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from infobim.project.domain.model.contract import ProjectContract
from infobim.project.plugin.machine.project_refresh.state import (
    ProjectRefreshProcessState,
)
from infobim.project.plugin.check.is_project_dataset_refreshed.hotfix import (
    main as refresh_project_dataset,
)


class ProjectDatasetRefreshedCapability(TransactionCapability):
    """
    Ensures the reserved InfoBIM dataset is re-validated, re-titled and
    re-indexed after the container refresh rewrites the manifest and
    datapackage.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.project.plugin.capability.transformation.target."
            "project_dataset_refreshed"
        ),
        version="1.0.0",
        name="Project Dataset Refreshed",
        description=(
            "Re-validate the reserved InfoBIM dataset after the "
            "container refresh rewrites the container manifest, "
            "re-write the dataset title and re-index the dataset entry "
            "on the container storage index."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "dataset", "refresh"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "The reserved InfoBIM dataset is re-validated and "
                    "re-indexed on the refreshed project container."
                ),
            },
            "debug_entry": {
                "en": (
                    "Refreshing the reserved InfoBIM dataset on the "
                    "refreshed project container."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Project Dataset Refreshed"

    def description(self, lang: str = "en") -> str:
        return (
            "Re-validates, re-titles and re-indexes the reserved "
            "InfoBIM dataset after the container refresh step."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path_value: Any = context.get_parameter_value("container_path")
        if not isinstance(project_path_value, str) or not project_path_value.strip():
            raise ValueError(
                "The project path is missing from the command context."
            )

        project_path: Path = Path(project_path_value).expanduser().resolve()
        exit_code: int = refresh_project_dataset(
            project_path=str(project_path),
            root_path=str(context.root_path),
        )
        if exit_code != 0:
            raise RuntimeError(
                f"Failed to refresh the reserved InfoBIM dataset in "
                f"the project at {project_path}."
            )

        dataset_path: Path = project_path / ProjectContract.DATASET_NAME

        return {
            "resulting_state": ProjectRefreshProcessState.PROJECT_DATASET_REFRESHED,
            "dataset_path": str(dataset_path),
            "exists": dataset_path.is_dir(),
        }
