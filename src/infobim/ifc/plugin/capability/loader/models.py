from pathlib import Path
from typing import Any, ClassVar, Dict, List, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.crate import ContainerRoCrate

from infobim.project.adapter.tree import ModelTree


class ContainerIfcModelsDataLoaderCapability(DataLoaderCapability):
    """Load the IFC-model branch declared by a project container's RO-Crate."""

    CAPABILITY_ID: ClassVar[str] = (
        "org.infobim.ifc.plugin.capability.loader.container.models"
    )
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    MODELS_KEY: ClassVar[str] = "models"
    MODEL_SUFFIXES: ClassVar[Tuple[str, ...]] = (
        ".ifc",
        ".ifczip",
        ".ifcz",
        ".ifcxml",
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=CAPABILITY_ID,
        version="1.0.0",
        name="Container IFC Models",
        description=(
            "List the IFC models a project container holds, read from the "
            "RO-Crate that states the files it carries."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "infobim",
            "project",
            "model",
            "ifc",
            "container",
            "data-loader",
            "read-only",
        ],
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
                MODELS_KEY: {"type": "object"},
            },
            "required": [CONTAINER_PATH_KEY, MODELS_KEY],
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang == "pt-br":
            return "Modelos IFC do Container"
        return "Container IFC Models"

    def description(self, lang: str = "en") -> str:
        if lang == "pt-br":
            return (
                "Lista os modelos IFC que um container de projeto contém, "
                "conforme declarado em seu RO-Crate."
            )
        return (
            "Lists the IFC models a project container holds, as its "
            "RO-Crate states them."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        lang: str = (
            context.language
            if context.language is not None
            else ModelTree.DEFAULT_LANGUAGE
        )

        return {
            self.CONTAINER_PATH_KEY: str(container_path),
            self.MODELS_KEY: ModelTree.of(
                self._models_of(container_path),
                lang,
            ),
        }

    @classmethod
    def _models_of(cls, container_path: Path) -> List[str]:
        return [
            file_path
            for file_path in ContainerRoCrate.file_paths(container_path)
            if any(
                file_path.lower().endswith(suffix)
                for suffix in cls.MODEL_SUFFIXES
            )
        ]
