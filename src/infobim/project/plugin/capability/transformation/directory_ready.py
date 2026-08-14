from pathlib import Path
from typing import Any, Dict

from infobim.project.domain.machine.project_state import ContainerCreateProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class DirectoryReadyCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.storage.plugin.capability.transformation.target.directory_ready",
        version="1.0.0",
        name="Directory Ready",
        description="Ensure that the target storage container directory exists.",
        author=["TRAE"],
        tags=["storage", "container", "create"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Directory Ready"

    def description(self, lang: str = "en") -> str:
        return "Creates the target directory for the InfoBIM storage container."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path_value: object = context.get_parameter_value("container_path")
        if not isinstance(target_path_value, str) or not target_path_value.strip():
            raise ValueError("Storage target path is missing from the command context.")

        target_path: Path = Path(target_path_value).expanduser().resolve()
        try:
            target_path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ValueError(f"Invalid storage target path: {target_path_value!r}.") from error

        return {
            "resulting_state": ContainerCreateProcessState.DIRECTORY_READY,
            "path": str(target_path),
            "exists": target_path.exists(),
        }
