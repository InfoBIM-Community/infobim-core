"""Set a straight linear IFC element's length in the project length unit."""

from __future__ import annotations

from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.plugin.capability.positioning.support import (
    PositioningCapabilityBase,
    PositioningSupport,
)


class LinearElementLengthCapability(PositioningCapabilityBase):
    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.positioning.linear_element_length",
        version="1.0.0",
        name="Linear Element Length",
        description=(
            "Set the positive length of a straight linear element in the project's "
            "declared length unit. The start point and direction are preserved, and the "
            "end point is recalculated."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "positioning", "linear", "length"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string", "required": True},
                "element_global_id": {"type": "string", "required": True},
                "l": {
                    "type": "number",
                    "required": True,
                    "description": "Positive length in the project length unit.",
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
                "old_length": {"type": "number"},
                "new_length": {"type": "number"},
                "project_unit_scale_to_si": {"type": "number"},
            },
        },
        log_message={
            "info": {
                "en": "The linear element length was updated.",
                "pt-br": "O comprimento do elemento linear foi atualizado.",
            },
            "debug_entry": {
                "en": "Updating length while preserving the linear element start point and direction.",
                "pt-br": "Atualizando o comprimento e preservando o ponto inicial e a direção do elemento linear.",
            },
        },
    )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import numpy as np

        if not context.has_parameter("l"):
            raise ValueError("'l' is required.")
        requested_length = float(context.get_parameter_value("l"))
        if requested_length <= PositioningSupport.EPSILON:
            raise ValueError("'l' must be greater than zero.")

        ifc_path, model, target = PositioningSupport.open_target(context)
        solid = PositioningSupport.linear_solid(target)
        start, old_end, direction = PositioningSupport.endpoints(target, solid)
        new_end_array = np.array(start, dtype=float) + np.array(direction) * requested_length
        new_end = tuple(float(value) for value in new_end_array)
        old_length = float(solid.Depth)
        new_length = PositioningSupport.set_endpoints(model, target, start, new_end)
        unit_scale = PositioningSupport.project_unit_scale_to_si(model)
        PositioningSupport.write(ifc_path, model)
        return {
            "ifc_path": str(ifc_path),
            "element_global_id": str(target.GlobalId),
            "start_point": list(start),
            "old_end_point": list(old_end),
            "new_end_point": list(new_end),
            "old_length": old_length,
            "new_length": new_length,
            "project_unit_scale_to_si": unit_scale,
        }
