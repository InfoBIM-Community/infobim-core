from pathlib import Path
from typing import Any, ClassVar, Dict, List, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.crate import ContainerRoCrate

from infobim.drawing.adapter.tree import DrawingTree


class ContainerDrawingsDataLoaderCapability(DataLoaderCapability):
    """Load the drawings branch declared by a container's RO-Crate."""

    CAPABILITY_ID: ClassVar[str] = (
        "org.infobim.drawing.plugin.capability.loader.container"
    )
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    DRAWINGS_KEY: ClassVar[str] = "drawings"
    DRAWING_SUFFIXES: ClassVar[Tuple[str, ...]] = (".dwg", ".dxf")

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=CAPABILITY_ID,
        version="1.0.0",
        name="Container Drawings",
        description=(
            "List the drawings a container holds, read from the RO-Crate "
            "that states the files it carries."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "drawing", "container", "data-loader", "read-only"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                CONTAINER_PATH_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                CONTAINER_PATH_KEY: {"type": "string"},
                DRAWINGS_KEY: {"type": "object"},
            },
            "required": [CONTAINER_PATH_KEY, DRAWINGS_KEY],
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Container Drawings"

    def description(self, lang: str = "en") -> str:
        return "Lists the drawings a container holds, as its RO-Crate states them."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        lang: str = (
            context.language
            if context.language is not None
            else DrawingTree.DEFAULT_LANGUAGE
        )

        return {
            self.CONTAINER_PATH_KEY: str(container_path),
            self.DRAWINGS_KEY: DrawingTree.of(
                self._drawings_of(container_path),
                lang,
            ),
        }

    @classmethod
    def _drawings_of(cls, container_path: Path) -> List[str]:
        return [
            file_path
            for file_path in ContainerRoCrate.file_paths(container_path)
            if file_path.lower().endswith(cls.DRAWING_SUFFIXES)
        ]
