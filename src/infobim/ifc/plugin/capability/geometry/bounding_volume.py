"""Attach the smallest supported bounding volume to one IFC element."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import ifcopenshell

from infobim.ifc.adapter.bounding_volume import (
    BoundingVolumeRepresentation,
    BoundingVolumeSelection,
    BoundingVolumeService,
)
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.atomic_file import AtomicFileWriter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class IfcBoundingVolumeCapability(TransactionCapability):
    """Create a secondary bounding representation on an existing IFC product."""

    METADATA = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.geometry.bounding_volume",
        version="1.0.0",
        name="IFC Bounding Volume",
        description=(
            "Fit a rectangular cuboid, a right circular cylinder and a sphere around "
            "one closed IFC Body, then create an IfcAnnotation containing the "
            "candidate with the least excess volume."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometry", "bounding-volume", "csg"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the IFC file that contains the element.",
                },
                "element_global_id": {
                    "type": "string",
                    "required": True,
                    "description": "GlobalId of the element whose Body will be bounded.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_path": {"type": "string"},
                "element_global_id": {"type": "string"},
                "selected_shape": {"type": "string"},
                "element_volume": {"type": "number"},
                "bounding_volume": {"type": "number"},
                "extra_volume": {"type": "number"},
                "extra_volume_ratio": {"type": "number"},
                "candidate_volumes": {"type": "object"},
                "representation_identifier": {"type": "string"},
                "representation_type": {"type": "string"},
                "annotation_global_id": {"type": "string"},
                "assignment_global_id": {"type": "string"},
                "project_unit_scale_to_si": {"type": "number"},
            },
        },
        log_message={
            "info": {
                "en": "An IFC annotation was created with the smallest supported bounding volume.",
                "pt-br": "Uma anotação IFC foi criada com o menor volume envolvente suportado.",
            },
            "debug_entry": {
                "en": "Fitting and comparing IFC bounding-volume representations.",
                "pt-br": "Ajustando e comparando representações IFC de volume envolvente.",
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

        global_id: str = str(
            context.get_parameter_value("element_global_id")
        ).strip()
        if not global_id:
            raise ValueError("'element_global_id' is required.")

        model: Any = ifcopenshell.open(str(ifc_path))
        try:
            target: Any = model.by_guid(global_id)
        except RuntimeError as error:
            raise ValueError(
                f"No IFC element with GlobalId '{global_id}' was found."
            ) from error
        if target is None:
            raise ValueError(f"No IFC element with GlobalId '{global_id}' was found.")

        service: BoundingVolumeService = BoundingVolumeService(model)
        selection: BoundingVolumeSelection = service.select(target)
        attached: BoundingVolumeRepresentation = service.attach(target, selection)
        AtomicFileWriter.write(ifc_path, lambda temporary: model.write(str(temporary)))

        candidate_volumes: Dict[str, float] = {
            candidate.kind.value: candidate.volume
            for candidate in selection.candidates
        }
        return {
            "ifc_path": str(ifc_path),
            "element_global_id": str(target.GlobalId),
            "selected_shape": selection.selected.kind.value,
            "element_volume": selection.element_volume,
            "bounding_volume": selection.selected.volume,
            "extra_volume": selection.extra_volume,
            "extra_volume_ratio": selection.extra_volume_ratio,
            "candidate_volumes": candidate_volumes,
            "representation_identifier": str(
                attached.shape_representation.RepresentationIdentifier
            ),
            "representation_type": str(
                attached.shape_representation.RepresentationType
            ),
            "annotation_global_id": str(attached.annotation.GlobalId),
            "assignment_global_id": str(attached.assignment.GlobalId),
            "project_unit_scale_to_si": selection.project_unit_scale_to_si,
        }
