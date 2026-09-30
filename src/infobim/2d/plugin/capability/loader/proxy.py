from typing import Any, Dict, Optional, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.adapter.open_file import (
    OPEN_FILE_INPUT_SCHEMA,
    OPEN_FILE_OUTPUT_SCHEMA,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport

from infobim._2d.adapter.capability import TwoDCapabilityLoader


class TwoDOpenFileCapabilityProxy(DataLoaderCapability, OpenFileChainSupport):
    """
    Delegates the open-file chain to capabilities under ``infobim._2d``.

    ``infobim._2d`` is a hidden package (its optional PySide6 stack), so
    the generic ``ChainResponsibilityLoader`` never finds a capability
    declared there directly. This proxy lives in the ordinary, discoverable
    ``infobim.2d`` package instead — the same split ``TwoDProxyCommand`` /
    ``TwoDCommandLoader`` already use for the ``2d`` commands — and stands
    in for whichever internal capability accepts the current file, without
    the open-file chain ever importing PySide6 or the private package itself.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.2d.plugin.capability.loader.open_file_proxy",
        version="1.0.0",
        name="2D Open File Proxy",
        description="Delegate the open-file chain to the internal infobim._2d package.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "open_file", "chain"],
        supported_languages=["en"],
        input_schema=OPEN_FILE_INPUT_SCHEMA,
        output_schema=OPEN_FILE_OUTPUT_SCHEMA,
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def can_handle(
        self,
        context: CliContextPort,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return self._resolve_target(context) is not None

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target: Optional[CapabilityPort] = self._resolve_target(context)
        if target is None:
            return {
                "handled": False,
                "handler": None,
                "message": "",
                "error": "No internal 2D capability accepted the file.",
            }

        return target.execute(context)

    @staticmethod
    def _resolve_target(context: CliContextPort) -> Optional[CapabilityPort]:
        logger: LogRepositoryPort = NullLogRepository()
        candidate_type: Type[CapabilityPort]
        for candidate_type in TwoDCapabilityLoader(logger).get_all(OpenFileChainSupport):
            candidate: CapabilityPort = candidate_type()
            if isinstance(candidate, OpenFileChainSupport) and candidate.can_handle(context):
                return candidate

        return None
