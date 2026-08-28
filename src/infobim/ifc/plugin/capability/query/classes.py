from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from infobim.ifc.adapter.class_catalog import IfcClassCatalogRepository
from infobim.ifc.plugin.capability.query.support import IfcProjectQueryCapability
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class IfcClassesQueryCapability(IfcProjectQueryCapability):
    """List the IFC classes exposed by all dataset facades in a Project."""

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.query.classes",
        version="1.0.0",
        name="Query IFC Classes",
        description=(
            "List deduplicated IFC classes and their element counts across "
            "the dataset facades of one InfoBIM Project."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "query", "class", "facade"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "class_count": {"type": "integer"},
                "element_count": {"type": "integer"},
                "classes": {"type": "array"},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path: Path = self.project_path(context)
        return IfcClassCatalogRepository(str(project_path)).list_classes()
