from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.adapter.repair import CheckedRepair
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from infobim.cli.adapter.shortcut import ServeShortcut
from infobim.cli.plugin.check.is_serve_shortcut_ready.check import (
    main as check_serve_shortcut_ready,
)
from infobim.cli.plugin.check.is_serve_shortcut_ready.hotfix import (
    main as hotfix_serve_shortcut_ready,
)
from infobim.cli.plugin.machine.init.state import InfoBIMInitProcessState


class ServeShortcutReadyCapability(TransactionCapability):
    """
    Puts the shortcut that starts ``infobim serve`` in the project root.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.cli.plugin.capability.transformation.target."
            "serve_shortcut_ready"
        ),
        version="1.0.0",
        name="Serve Shortcut Ready",
        description=(
            "Ensure the project root holds the shortcut that runs infobim "
            "serve from the project folder."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "init", "serve", "shortcut"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The InfoBIM serve shortcut is in place in the project root.",
            },
            "debug_entry": {
                "en": "Putting the InfoBIM serve shortcut in the project root.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return InfoBIMInitProcessState.SERVE_SHORTCUT_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return InfoBIMInitProcessState.SERVE_SHORTCUT_READY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        CheckedRepair.ensure(
            check_serve_shortcut_ready,
            hotfix_serve_shortcut_ready,
            root_path,
            ServeShortcut.FILE_NAME,
        )
        return {
            "resulting_state": InfoBIMInitProcessState.SERVE_SHORTCUT_READY,
            "serve_shortcut": ServeShortcut(root_path).describe(),
        }
