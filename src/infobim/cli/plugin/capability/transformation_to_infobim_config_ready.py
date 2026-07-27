from typing import Any, Dict

from infobim.cli.domain.machine import InfoBIMInitProcessState
from infobim.cli.plugin.check.has_valid_infobim_config.check import main as check_infobim_config
from infobim.cli.plugin.check.has_valid_infobim_config.hotfix import main as hotfix_infobim_config
from infobim.shared.adapter.config import ConfigDataAdapter
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import get_init_root_path


class InfoBIMConfigReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.infobim_config_ready",
        version="1.0.0",
        name="InfoBIM Config Ready",
        description="Ensure that the InfoBIM configuration directory and config.yaml are available for the CLI init flow.",
        author=["TRAE"],
        tags=["cli", "init", "infobim", "config"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "InfoBIM Config Ready"

    def description(self, lang: str = "en") -> str:
        return "Repairs and validates the InfoBIM config directory and the default IFC schema."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path = get_init_root_path(context=context)
        if check_infobim_config(root_path=str(root_path)) != 0:
            if hotfix_infobim_config(root_path=str(root_path)) != 0:
                raise ValueError("Failed to hotfix InfoBIM config during CLI init.")

        if check_infobim_config(root_path=str(root_path)) != 0:
            raise ValueError("InfoBIM config is still invalid after the CLI init hotfix.")

        config_adapter: ConfigDataAdapter = ConfigDataAdapter(root_dir=str(root_path))
        prefered_schema: str = str(config_adapter.infobim_config.get("ifc", {}).get("preferedSchema"))
        return {
            "resulting_state": InfoBIMInitProcessState.INFOBIM_CONFIG_READY,
            "prefered_schema": prefered_schema,
        }
