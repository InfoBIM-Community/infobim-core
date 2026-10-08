from pathlib import Path
from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import DataLoaderCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.project.adapter.tree import InfoTree


class ProjectInfoDataLoaderCapability(DataLoaderCapability):
    """Load the Info branch of a project: the attributes of its IfcProject."""

    CAPABILITY_ID: ClassVar[str] = "org.infobim.project.plugin.capability.loader.info"
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    INFO_KEY: ClassVar[str] = "info"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=CAPABILITY_ID,
        version="1.0.0",
        name="Project Info",
        description=(
            "List the attributes of the IfcProject a project declares, each "
            "with its values."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "project", "info", "ifc-project", "data-loader", "read-only"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                CONTAINER_PATH_KEY: {"type": "string", "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                CONTAINER_PATH_KEY: {"type": "string"},
                INFO_KEY: {"type": "object"},
            },
            "required": [CONTAINER_PATH_KEY, INFO_KEY],
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang == "pt-br":
            return "Info do Projeto"
        return "Project Info"

    def description(self, lang: str = "en") -> str:
        if lang == "pt-br":
            return "Lista os atributos do IfcProject que um projeto declara, cada um com seus valores."
        return "Lists the attributes of the IfcProject a project declares, each with its values."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        lang: str = (
            context.language
            if context.language is not None
            else InfoTree.DEFAULT_LANGUAGE
        )

        return {
            self.CONTAINER_PATH_KEY: str(container_path),
            self.INFO_KEY: InfoTree.of(container_path, lang),
        }
