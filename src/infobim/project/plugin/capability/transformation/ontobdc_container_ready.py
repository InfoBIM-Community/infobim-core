from typing import Any, Dict

from infobim.project.plugin.capability.base import ProjectTransactionCapability
from infobim.project.plugin.check.is_ontobdc_container_ready import evaluate
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.machine import ContainerCreateStateTransitionHandler


class OntoBDCContainerReadyCapability(ProjectTransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.ontobdc_container_ready",
        version="1.0.0",
        name="OntoBDC Container Ready",
        description="Ensure the project path is a ready OntoBDC container.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "ontobdc", "container"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Project path was created or validated as an OntoBDC container "
                    "ready for downstream InfoBIM steps."
                ),
            },
            "debug_entry": {
                "en": (
                    "Creating or validating the project path as an OntoBDC "
                    "container ready for downstream InfoBIM steps."
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
        if not self.is_satisfied(context):
            ContainerCreateStateTransitionHandler(context=context).execute()
        if not self.is_satisfied(context):
            raise ValueError("OntoBDC container lifecycle did not reach ready state.")
        return {"container_path": str(context.get_parameter_value("container_path")), "satisfied": True}
