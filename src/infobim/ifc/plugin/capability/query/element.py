from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from infobim.ifc.adapter.class_catalog import IfcClassCatalogRepository
from infobim.ifc.plugin.capability.query.support import IfcProjectQueryCapability
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class IfcElementQueryCapability(IfcProjectQueryCapability):
    """Resolve one facade-backed IFC element by GlobalId in a Project."""

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.query.element",
        version="1.0.0",
        name="Query IFC Element",
        description=(
            "Resolve one IFC element by GlobalId across the dataset facades "
            "of one InfoBIM Project."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "query", "element", "facade"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "required": True},
                "element_global_id": {"type": "string", "required": True},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "project_path": {"type": "string"},
                "global_id": {"type": "string"},
                "found": {"type": "boolean"},
                "class_uri": {"type": ["string", "null"]},
                "class_name": {"type": ["string", "null"]},
                "dataset_count": {"type": "integer"},
                "datasets": {"type": "array"},
                "element": {"type": ["object", "null"]},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        project_path: Path = self.project_path(context)
        global_id: str = self.required_text(context, "element_global_id")
        return IfcClassCatalogRepository(str(project_path)).get_element(global_id)
