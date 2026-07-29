from pathlib import Path
from typing import Any, Dict

from infobim.cli.plugin.check.has_valid_infobim_config.check import (
    main as check_infobim_config,
)
from infobim.cli.plugin.check.has_valid_infobim_config.hotfix import (
    main as hotfix_infobim_config,
)
from infobim.project.domain.machine.project_state import ContainerCreateProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class InfoBIMConfigReadyCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.storage.plugin.capability.transformation.target.infobim_config_ready",
        version="1.0.0",
        name="InfoBIM Config Ready",
        description="Ensure that the project root has a valid InfoBIM configuration before the container creation flow continues.",
        author=["TRAE"],
        tags=["storage", "container", "create", "infobim", "config"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "InfoBIM Config Ready"

    def description(self, lang: str = "en") -> str:
        return "Creates and validates the root InfoBIM configuration required by the project container flow."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: str = str(Path(context.root_path).expanduser().resolve())
        if check_infobim_config(root_path=root_path) != 0:
            if hotfix_infobim_config(root_path=root_path) != 0:
                raise ValueError("Failed to hotfix the root InfoBIM configuration during project creation.")

        if check_infobim_config(root_path=root_path) != 0:
            raise ValueError("The root InfoBIM configuration is still invalid after the project creation hotfix.")

        config_file: Path = Path(root_path) / "__infobim__" / "config.yaml"
        return {
            "resulting_state": ContainerCreateProcessState.INFOBIM_CONFIG_READY,
            "root_path": root_path,
            "config_file": str(config_file),
        }
