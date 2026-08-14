from pathlib import Path
from typing import Any, Dict

from infobim.project.domain.machine.project_state import ContainerCreateProcessState
from infobim.project.plugin.check.is_project_ready.check import main as check_project_ready
from infobim.project.plugin.check.is_project_ready.hotfix import main as hotfix_project_ready
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class ProjectReadyCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.storage.plugin.capability.transformation.target.project_ready",
        version="1.0.0",
        name="Project Ready",
        description="Ensure that the InfoBIM project configuration exists in the target container.",
        author=["TRAE"],
        tags=["storage", "container", "create", "project", "infobim"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project Ready"

    def description(self, lang: str = "en") -> str:
        return "Creates and validates the InfoBIM project configuration inside the target container."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path: str = str(context.get_parameter_value("container_path")).strip()
        if check_project_ready(container_path=target_path) != 0:
            if hotfix_project_ready(container_path=target_path) != 0:
                raise ValueError("Failed to hotfix the InfoBIM project configuration during storage container creation.")

        if check_project_ready(container_path=target_path) != 0:
            raise ValueError("The InfoBIM project configuration is still invalid after the storage container hotfix.")

        return {
            "resulting_state": ContainerCreateProcessState.PROJECT_READY,
            "path": target_path,
            "project_file": str(Path(target_path) / ".__ontobdc__" / "__infobim__" / "project.ttl"),
        }
