"""Move one IFC product by project-unit offsets on one or more axes."""

from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.plugin.capability.positioning.support import (
    PositioningCapabilityBase,
    PositioningSupport,
)


class PositioningMoveCapability(PositioningCapabilityBase):
    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.positioning.move",
        version="1.0.0",
        name="Move",
        description=(
            "Move one IFC product by relative X, Y and/or Z offsets expressed in the "
            "project's declared length unit. At least one axis is required; omitted axes "
            "remain unchanged."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "positioning", "move", "placement"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string", "required": True},
                "element_global_id": {"type": "string", "required": True},
                "x": {
                    "type": "number",
                    "required": False,
                    "description": "Relative X offset in the project length unit.",
                },
                "y": {
                    "type": "number",
                    "required": False,
                    "description": "Relative Y offset in the project length unit.",
                },
                "z": {
                    "type": "number",
                    "required": False,
                    "description": "Relative Z offset in the project length unit.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "element_global_id": {"type": "string"},
                "offset": {"type": "array"},
                "old_position": {"type": "array"},
                "new_position": {"type": "array"},
                "project_unit_scale_to_si": {"type": "number"},
            },
        },
        log_message={
            "info": {"en": "The IFC element was moved.", "pt-br": "O elemento IFC foi movido."},
            "debug_entry": {
                "en": "Applying relative project-unit offsets to the element placement.",
                "pt-br": "Aplicando deslocamentos relativos na unidade do projeto ao posicionamento do elemento.",
            },
        },
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        values = PositioningSupport.partial_coordinates(context)
        ifc_path, model, target = PositioningSupport.open_target(context)
        old_position, new_position = PositioningSupport.move(model, target, values)
        unit_scale = PositioningSupport.project_unit_scale_to_si(model)
        PositioningSupport.write(ifc_path, model)
        return {
            "ifc_path": str(ifc_path),
            "element_global_id": str(target.GlobalId),
            "offset": [values.get(axis, 0.0) for axis in PositioningSupport.AXES],
            "old_position": list(old_position),
            "new_position": list(new_position),
            "project_unit_scale_to_si": unit_scale,
        }
