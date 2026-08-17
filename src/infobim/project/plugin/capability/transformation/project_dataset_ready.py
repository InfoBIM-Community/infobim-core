from pathlib import Path
from typing import Any, Dict

from infobim.project.domain.model.contract import PROJECT_DATASET_NAME
from infobim.project.plugin.capability.base import ProjectTransactionCapability
from infobim.project.plugin.check.is_project_dataset_ready import evaluate
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.machine import DatasetCreateStateTransitionHandler


class ProjectDatasetReadyCapability(ProjectTransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.project_dataset_ready",
        version="1.0.0",
        name="Project Dataset Ready",
        description="Ensure the reserved .__infobim__ project EntityDataset exists and is indexed by the OntoBDC container.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "dataset"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Reserved InfoBIM project EntityDataset was created or validated "
                    "and indexed by the OntoBDC container."
                ),
            },
            "debug_entry": {
                "en": (
                    "Creating or validating the reserved InfoBIM project "
                    "EntityDataset and indexing it into the OntoBDC container."
                ),
            },
        },
    )

    def is_satisfied(self, context: CliContextPort) -> bool:
        return evaluate(
            container_path=str(context.get_parameter_value("container_path")),
            root_path=str(context.root_path),
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path = Path(str(context.get_parameter_value("container_path"))).expanduser().resolve()
        dataset_path = container_path / PROJECT_DATASET_NAME
        context.set_parameter_value("dataset_path", str(dataset_path))
        if not self.is_satisfied(context):
            DatasetCreateStateTransitionHandler(context=context).execute()
        if not self.is_satisfied(context):
            raise ValueError("InfoBIM project dataset lifecycle did not reach ready state.")
        return {"dataset_path": str(dataset_path), "satisfied": True}
