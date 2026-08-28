"""Measure distances between IFC bounding-volume geometric centers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import ifcopenshell

from infobim.ifc.adapter.linear_distance import (
    BoundingVolumeLinearDistanceService,
    LinearDistanceMeasurement,
    LinearDistanceMode,
)
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import QueryCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class IfcBoundingVolumeLinearDistanceCapability(QueryCapability):
    """Measure two InfoBIM bounding-volume annotation centers."""

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.measurement.bounding_volume_linear_distance",
        version="1.0.0",
        name="IFC Bounding Volume Linear Distance",
        description=(
            "Measure the geometric centers of two InfoBIM bounding-volume annotations "
            "either along the direct 3D line or between parallel planes normal to a "
            "selected global X, Y or Z axis."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "measurement", "distance", "bounding-volume"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string", "required": True},
                "first_bounding_volume_global_id": {
                    "type": "string",
                    "required": True,
                },
                "second_bounding_volume_global_id": {
                    "type": "string",
                    "required": True,
                },
                "measurement_mode": {
                    "type": "string",
                    "required": True,
                    "description": "STRAIGHT_LINE or PARALLEL_PLANES.",
                },
                "axis": {
                    "type": "string",
                    "required": False,
                    "description": (
                        "Global x, y or z axis. Required only for PARALLEL_PLANES."
                    ),
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "measurement_mode": {"type": "string"},
                "axis": {"type": ["string", "null"]},
                "first_bounding_volume_global_id": {"type": "string"},
                "second_bounding_volume_global_id": {"type": "string"},
                "first_shape_kind": {"type": "string"},
                "second_shape_kind": {"type": "string"},
                "first_center": {"type": "array"},
                "second_center": {"type": "array"},
                "measurement_vector": {"type": "array"},
                "distance": {"type": "number"},
                "signed_distance": {"type": ["number", "null"]},
                "plane_normal": {"type": ["array", "null"]},
                "project_unit_scale_to_si": {"type": "number"},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return str(self.METADATA.name)

    def description(self, lang: str = "en") -> str:
        return str(self.METADATA.description)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ifc_path: Path = Path(
            str(context.get_parameter_value("ifc_path"))
        ).expanduser().resolve()
        if not ifc_path.is_file():
            raise ValueError(f"IFC file does not exist: {ifc_path}")

        first_global_id: str = str(
            context.get_parameter_value("first_bounding_volume_global_id")
        ).strip()
        second_global_id: str = str(
            context.get_parameter_value("second_bounding_volume_global_id")
        ).strip()
        if not first_global_id or not second_global_id:
            raise ValueError("Both bounding-volume GlobalIds are required.")
        raw_mode: str = str(context.get_parameter_value("measurement_mode")).strip().upper()
        try:
            mode: LinearDistanceMode = LinearDistanceMode(raw_mode)
        except ValueError as error:
            raise ValueError(
                "'measurement_mode' must be STRAIGHT_LINE or PARALLEL_PLANES."
            ) from error
        axis: Optional[str] = (
            str(context.get_parameter_value("axis"))
            if context.has_parameter("axis")
            else None
        )

        model: Any = ifcopenshell.open(str(ifc_path))
        measurement: LinearDistanceMeasurement = BoundingVolumeLinearDistanceService(
            model
        ).measure(first_global_id, second_global_id, mode, axis)
        return {
            "ifc_path": str(ifc_path),
            "measurement_mode": measurement.mode.value,
            "axis": measurement.axis,
            "first_bounding_volume_global_id": measurement.first.annotation_global_id,
            "second_bounding_volume_global_id": measurement.second.annotation_global_id,
            "first_shape_kind": measurement.first.shape_kind,
            "second_shape_kind": measurement.second.shape_kind,
            "first_center": list(measurement.first.point),
            "second_center": list(measurement.second.point),
            "measurement_vector": list(measurement.vector),
            "distance": measurement.distance,
            "signed_distance": measurement.signed_distance,
            "plane_normal": (
                None
                if measurement.plane_normal is None
                else list(measurement.plane_normal)
            ),
            "project_unit_scale_to_si": measurement.project_unit_scale_to_si,
        }
