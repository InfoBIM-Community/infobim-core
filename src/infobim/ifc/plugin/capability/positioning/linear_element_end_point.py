"""Set selected coordinates of a straight linear IFC element's end point."""

from __future__ import annotations

from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.plugin.capability.positioning.support import (
    PositioningCapabilityBase,
    PositioningSupport,
)


class LinearElementEndPointCapability(PositioningCapabilityBase):
    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.positioning.linear_element_end_point",
        version="1.0.0",
        name="Linear Element End Point",
        description=(
            "Set one or more absolute coordinates of a straight linear element's end "
            "point in the project length unit. At least one of X, Y or Z is required. "
            "Omitted coordinates and the start point are preserved. The end point can "
            "never be equal to or before the start point along the element direction."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "positioning", "linear", "end-point"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string", "required": True},
                "element_global_id": {"type": "string", "required": True},
                "x": {
                    "type": "number",
                    "required": False,
                    "description": "Absolute end-point X in the project length unit.",
                },
                "y": {
                    "type": "number",
                    "required": False,
                    "description": "Absolute end-point Y in the project length unit.",
                },
                "z": {
                    "type": "number",
                    "required": False,
                    "description": "Absolute end-point Z in the project length unit.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "element_global_id": {"type": "string"},
                "start_point": {"type": "array"},
                "old_end_point": {"type": "array"},
                "new_end_point": {"type": "array"},
                "length": {"type": "number"},
                "project_unit_scale_to_si": {"type": "number"},
            },
        },
        log_message={
            "info": {
                "en": "The linear element end point was updated.",
                "pt-br": "O ponto final do elemento linear foi atualizado.",
            },
            "debug_entry": {
                "en": "Updating selected end-point coordinates while preserving the start point.",
                "pt-br": "Atualizando coordenadas selecionadas do ponto final e preservando o ponto inicial.",
            },
        },
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        values = PositioningSupport.partial_coordinates(context)
        ifc_path, model, target = PositioningSupport.open_target(context)
        solid = PositioningSupport.linear_solid(target)
        start, old_end, direction = PositioningSupport.endpoints(target, solid)
        new_end = PositioningSupport.merge_coordinates(old_end, values)
        PositioningSupport.ensure_forward(start, new_end, direction)
        length = PositioningSupport.set_endpoints(model, target, start, new_end)
        unit_scale = PositioningSupport.project_unit_scale_to_si(model)
        PositioningSupport.write(ifc_path, model)
        return {
            "ifc_path": str(ifc_path),
            "element_global_id": str(target.GlobalId),
            "start_point": list(start),
            "old_end_point": list(old_end),
            "new_end_point": list(new_end),
            "length": length,
            "project_unit_scale_to_si": unit_scale,
        }
