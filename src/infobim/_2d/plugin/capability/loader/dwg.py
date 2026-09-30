from pathlib import Path
from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.adapter.open_file import (
    OPEN_FILE_INPUT_SCHEMA,
    OPEN_FILE_OUTPUT_SCHEMA,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport


class DwgOpenFileCapability(DataLoaderCapability, OpenFileChainSupport):
    """Stub for the optional DWG open-file capability."""

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim._2d.plugin.capability.loader.dwg",
        version="1.0.0",
        name="Open DWG File",
        description="Open a local DWG file.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "2d", "open_file", "chain", "dwg"],
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
        raw_path: Any = context.get_parameter_value(self.PATH_KEY)
        if not isinstance(raw_path, str) or not raw_path.strip():
            return False

        return Path(raw_path.strip()).suffix.lower() == ".dwg"

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raise NotImplementedError("DwgOpenFileCapability is a stub.")
