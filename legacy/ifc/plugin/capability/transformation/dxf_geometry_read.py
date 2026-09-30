from pathlib import Path
from typing import Any, Dict

import ezdxf

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.plugin.machine.dxf_import.state import (
    IfcImportContextKeys,
    IfcImportProcessState,
)


class DxfGeometryReadCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "dxf_geometry_read"
        ),
        version="0.1.0",
        name="DXF Geometry Read",
        description="Read the DXF modelspace and summarize its entity geometry.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "dxf", "geometry", "import"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                IfcImportContextKeys.DXF_SOURCE_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                IfcImportContextKeys.DXF_GEOMETRY_KEY: {"type": "object"},
            },
            "required": [IfcImportContextKeys.DXF_GEOMETRY_KEY],
        },
    )

    def label(self, lang: str = "en") -> str:
        return IfcImportProcessState.DXF_GEOMETRY_READ.label(lang)

    def description(self, lang: str = "en") -> str:
        return "Read the DXF modelspace and summarize its entity geometry."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw: Any = context.get_parameter_value(
            IfcImportContextKeys.DXF_SOURCE_KEY
        )
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Resolved DXF source is missing.")

        source = Path(raw).expanduser().resolve()
        try:
            document = ezdxf.readfile(source)
        except (IOError, ezdxf.DXFError) as error:
            raise ValueError(
                f"Could not read DXF source: {source}: {error}"
            ) from error

        entity_types: Dict[str, int] = {}
        entity_count = 0
        for entity in document.modelspace():
            entity_count += 1
            name = entity.dxftype()
            entity_types[name] = entity_types.get(name, 0) + 1

        summary: Dict[str, Any] = {
            "entity_count": entity_count,
            "entity_types": entity_types,
        }
        context.set_parameter_value(
            IfcImportContextKeys.DXF_GEOMETRY_KEY,
            summary,
        )
        return {
            "resulting_state": IfcImportProcessState.DXF_GEOMETRY_READ,
            IfcImportContextKeys.DXF_GEOMETRY_KEY: summary,
        }
