from typing import Any, Dict

from infobim.project.domain.machine.project_state import ContainerCreateProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)
from ontobdc.storage.plugin.check.is_container_storage_index_ready.hotfix import (
    main as hotfix_container_storage_index_ready,
)


class ContainerStorageIndexReadyCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.storage.plugin.capability.transformation.target.container_storage_index_ready",
        version="1.0.0",
        name="Container Storage Index Ready",
        description="Ensure that storage.ttl is synchronized with the container metadata file for the target container.",
        author=["TRAE"],
        tags=["storage", "container", "create", "index"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Container Storage Index Ready"

    def description(self, lang: str = "en") -> str:
        return "Synchronizes storage.ttl container entry with the container.ttl metadata."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path: str = str(context.get_parameter_value("container_path")).strip()
        root_path: str = str(context.root_path).strip()
        if check_container_storage_index_ready(
            container_path=target_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_storage_index_ready(
                container_path=target_path,
                root_path=root_path,
            ) != 0:
                raise ValueError("Failed to hotfix storage index entry during InfoBIM storage container creation.")

        if check_container_storage_index_ready(
            container_path=target_path,
            root_path=root_path,
        ) != 0:
            raise ValueError("Storage index entry is still invalid after the InfoBIM storage container hotfix.")

        return {
            "resulting_state": ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY,
            "path": target_path,
        }
