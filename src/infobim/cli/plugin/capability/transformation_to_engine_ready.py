from typing import Any, Dict

from infobim.cli.domain.machine import InfoBIMInitProcessState
from infobim.cli.plugin.check.has_valid_engine.check import main as check_engine
from infobim.cli.plugin.check.has_valid_engine.hotfix import main as hotfix_engine
from infobim.shared.adapter.config import ConfigDataAdapter
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import get_init_root_path


class EngineReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.engine_ready",
        version="1.0.0",
        name="Engine Ready",
        description="Ensure that the project engine is configured and valid for the InfoBIM CLI init flow.",
        author=["TRAE"],
        tags=["cli", "init", "engine"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Engine Ready"

    def description(self, lang: str = "en") -> str:
        return "Repairs and validates the engine entry in the bootstrap config."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path = get_init_root_path(context=context)
        if check_engine(root_path=str(root_path)) != 0:
            if hotfix_engine(root_path=str(root_path)) != 0:
                raise ValueError("Failed to hotfix engine during CLI init.")

        if check_engine(root_path=str(root_path)) != 0:
            raise ValueError("engine is still invalid after the CLI init hotfix.")

        config_adapter: ConfigDataAdapter = ConfigDataAdapter(root_dir=str(root_path))
        engine: str = str(config_adapter.all.get("engine"))
        return {
            "resulting_state": InfoBIMInitProcessState.ENGINE_READY,
            "engine": engine,
        }
