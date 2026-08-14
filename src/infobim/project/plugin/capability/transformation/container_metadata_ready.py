from typing import Any, Dict

from infobim.project.domain.machine.project_state import ContainerCreateProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.storage.plugin.check.is_container_metadata_ready.hotfix import (
    main as hotfix_container_metadata_ready,
)


class ContainerMetadataReadyCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.storage.plugin.capability.transformation.target.container_metadata_ready",
        version="1.0.0",
        name="Container Metadata Ready",
        description="Ensure that the target storage container metadata file exists with valid container metadata.",
        author=["TRAE"],
        tags=["storage", "container", "create", "metadata"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Container Metadata Ready"

    def description(self, lang: str = "en") -> str:
        return "Creates the local container metadata file without requiring dataset relations."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path: str = str(context.get_parameter_value("container_path")).strip()
        root_path: str = str(context.root_path).strip()
        if check_container_metadata_ready(
            container_path=target_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_metadata_ready(
                container_path=target_path,
                root_path=root_path,
            ) != 0:
                raise ValueError("Failed to hotfix container metadata during InfoBIM storage container creation.")

        if check_container_metadata_ready(
            container_path=target_path,
            root_path=root_path,
        ) != 0:
            raise ValueError("Container metadata is still invalid after the InfoBIM storage container hotfix.")

        return {
            "resulting_state": ContainerCreateProcessState.CONTAINER_METADATA_READY,
            "path": target_path,
        }
