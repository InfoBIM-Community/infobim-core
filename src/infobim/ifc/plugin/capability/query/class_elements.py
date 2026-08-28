from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from infobim.ifc.adapter.class_catalog import IfcClassCatalogRepository
from infobim.ifc.plugin.capability.query.support import IfcProjectQueryCapability
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class IfcClassElementsQueryCapability(IfcProjectQueryCapability):
    """List the elements exposed for one IFC class in a Project."""

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.query.class_elements",
        version="1.0.0",
        name="Query IFC Class Elements",
        description=(
            "List deduplicated elements of one IFC class across the dataset "
            "facades of one InfoBIM Project."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "query", "class", "element", "facade"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "required": True},
                "ifc_class": {"type": "string", "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "class_name": {"type": "string"},
                "class_uri": {"type": ["string", "null"]},
                "dataset_count": {"type": "integer"},
                "datasets": {"type": "array"},
                "element_count": {"type": "integer"},
                "elements": {"type": "array"},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path: Path = self.project_path(context)
        ifc_class: str = self.required_text(context, "ifc_class")
        return IfcClassCatalogRepository(str(project_path)).list_elements(ifc_class)
