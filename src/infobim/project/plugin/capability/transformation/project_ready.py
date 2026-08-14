from typing import Any, Dict

from infobim.project.plugin.capability.base import ProjectTransactionCapability
from infobim.project.plugin.check.is_project_ready import evaluate
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.machine import ContainerCreateStateTransitionHandler


class ProjectReadyCapability(ProjectTransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.project_ready",
        version="1.0.0",
        name="Project Ready",
        description="Validate the complete InfoBIM project contract and resynchronize the underlying OntoBDC container after project artifacts are materialized.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "ready"],
        supported_languages=["en", "pt-br"],
    )

    def is_satisfied(self, context: CliContextPort) -> bool:
        return evaluate(
            container_path=str(context.get_parameter_value("container_path")),
            root_path=str(context.root_path),
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        if not self.is_satisfied(context):
            ContainerCreateStateTransitionHandler(context=context).execute()
        if not self.is_satisfied(context):
            raise ValueError("InfoBIM project contract is not satisfied after OntoBDC container resynchronization.")
        context.set_parameter_value("project_ready", True)
        return {
            "container_path": str(context.get_parameter_value("container_path")),
            "satisfied": True,
        }
