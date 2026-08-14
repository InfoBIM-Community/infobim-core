from pathlib import Path
from typing import Any, Dict

from infobim.project.adapter.updated import (
    check_project_container_updated,
    hotfix_project_container_updated,
)
from infobim.project.domain.machine.import_state import ElementImportProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import get_container_crate_metadata_file_path


class UpdatedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.infobim.project.plugin.capability.transformation.target.updated",
        version="1.0.0",
        name="Project element import transformation to Updated",
        description="Ensure the target project container is updated and its RO-Crate metadata is synchronized.",
        author=["TRAE"],
        tags=["project", "import", "updated", "rocrate"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Project element import transformation to Updated"

    def description(self, lang: str = "en") -> str:
        return "Ensure the target project container is updated and its RO-Crate metadata is synchronized."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: str = str(context.get_parameter_value("container_path")).strip()
        root_path: str = str(context.root_path).strip()
        if check_project_container_updated(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            if hotfix_project_container_updated(
                container_path=container_path,
                root_path=root_path,
            ) != 0:
                raise ValueError("Failed to update the target project container before import.")

        if check_project_container_updated(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            raise ValueError("The target project container is still invalid after the import update hotfix.")

        crate_file: Path = get_container_crate_metadata_file_path(Path(container_path).expanduser().resolve())
        context.set_parameter_value("crate_file", str(crate_file))
        return {
            "resulting_state": ElementImportProcessState.UPDATED,
            "container_path": container_path,
            "crate_file": str(crate_file),
        }
