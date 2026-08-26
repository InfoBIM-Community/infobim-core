"""Set selected coordinates of a straight linear IFC element's start point."""

from __future__ import annotations

from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.plugin.capability.positioning.support import (
    PositioningCapabilityBase,
    PositioningSupport,
)


class LinearElementStartPointCapability(PositioningCapabilityBase):
    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.positioning.linear_element_start_point",
        version="1.0.0",
        name="Linear Element Start Point",
        description=(
            "Set one or more absolute coordinates of a straight linear element's start "
            "point in the project length unit. At least one of X, Y or Z is required. "
            "Omitted coordinates and the end point are preserved; changes that would "
            "place the end before the start are rejected."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "positioning", "linear", "start-point"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string", "required": True},
                "element_global_id": {"type": "string", "required": True},
                "x": {
                    "type": "number",
                    "required": False,
                    "description": "Absolute start-point X in the project length unit.",
                },
                "y": {
                    "type": "number",
                    "required": False,
                    "description": "Absolute start-point Y in the project length unit.",
                },
                "z": {
                    "type": "number",
                    "required": False,
                    "description": "Absolute start-point Z in the project length unit.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "element_global_id": {"type": "string"},
                "old_start_point": {"type": "array"},
                "new_start_point": {"type": "array"},
                "end_point": {"type": "array"},
                "length": {"type": "number"},
                "project_unit_scale_to_si": {"type": "number"},
            },
        },
        log_message={
            "info": {
                "en": "The linear element start point was updated.",
                "pt-br": "O ponto inicial do elemento linear foi atualizado.",
            },
            "debug_entry": {
                "en": "Updating selected start-point coordinates while preserving the end point.",
                "pt-br": "Atualizando coordenadas selecionadas do ponto inicial e preservando o ponto final.",
            },
        },
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        values = PositioningSupport.partial_coordinates(context)
        ifc_path, model, target = PositioningSupport.open_target(context)
        solid = PositioningSupport.linear_solid(target)
        old_start, end, direction = PositioningSupport.endpoints(target, solid)
        new_start = PositioningSupport.merge_coordinates(old_start, values)
        PositioningSupport.ensure_forward(new_start, end, direction)
        length = PositioningSupport.set_endpoints(model, target, new_start, end)
        unit_scale = PositioningSupport.project_unit_scale_to_si(model)
        PositioningSupport.write(ifc_path, model)
        return {
            "ifc_path": str(ifc_path),
            "element_global_id": str(target.GlobalId),
            "old_start_point": list(old_start),
            "new_start_point": list(new_start),
            "end_point": list(end),
            "length": length,
            "project_unit_scale_to_si": unit_scale,
        }
