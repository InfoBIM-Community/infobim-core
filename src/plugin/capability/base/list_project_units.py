
import os
import json
import argparse
import ifcopenshell
import ifcopenshell.util.unit
from rich.console import Console
from typing import Dict, Any, Optional
from stack.src.bib.core.capability.executor import CapabilityExecutor
from stack.src.tui.terminal.adapter.table_view import TableViewAdapter
from stack.src.bib.core.capability import Capability, CapabilityMetadata
from stack.src.bib.adapter.capability.cli.list_project_units import ProjectUnitsCliStrategy


class ProjectUnitsCapability(Capability):
    METADATA = CapabilityMetadata(
        id="org.infobim.base.capability.list_project_units",
        version="0.1.0",
        name="Project Units",
        description="Detects IFC project units and scales (length).",
        author="InfoBIM Team",
        tags=["ifc", "units", "detection"],
        supported_languages=["en", "pt_BR"],
        supported_ifc_formats=["IFC2X3", "IFC4"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "required": True,
                    "description": "Absolute path to the IFC file"
                }
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "length_unit": {"type": "string", "description": "IFC length unit name"},
                "length_scale": {"type": "number", "description": "Scale factor to meters"},
                "schema": {"type": "string", "description": "IFC schema version"},
                "units": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "unit_type": {"type": "string"},
                            "name": {"type": "string"},
                            "prefix": {"type": "string"},
                            "kind": {"type": "string"},
                            "elements_count": {"type": "integer"}
                        }
                    },
                    "description": "All units attached to IfcProject.UnitsInContext"
                }
            }
        },
        raises=[
            {
                "code": "org.ontobdc.aeco.base.exception.file_not_found",
                "python_type": "FileNotFoundError",
                "description": "IFC file not found"
            },
            {
                "code": "org.ontobdc.aeco.base.exception.unit_detection_error",
                "python_type": "ValueError",
                "description": "Error detecting project units"
            }
        ]
    )

    def get_default_cli_strategy(self, **kwargs) -> Optional[Any]:
        return ProjectUnitsCliStrategy(**kwargs)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ifc_path = inputs.get("ifc_path")
        ifc_file = ifcopenshell.open(ifc_path)
        scale = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)
        length_unit_name = "METRE"
        try:
            proj = ifc_file.by_type("IfcProject")
            ua = None
            if proj:
                ua = proj[0].UnitsInContext
            if not ua:
                assigns = ifc_file.by_type("IfcUnitAssignment")
                if assigns:
                    ua = assigns[0]
            units_list = []
            if ua and ua.Units:
                for u in ua.Units:
                    unit_type = None
                    name = None
                    prefix = None
                    kind = None
                    elements_count = 0
                    if hasattr(u, "UnitType"):
                        unit_type = str(u.UnitType) if u.UnitType else None
                    if u.is_a("IfcSIUnit"):
                        name = str(u.Name) if u.Name else None
                        prefix = str(u.Prefix) if u.Prefix else None
                        kind = "SI"
                    elif u.is_a("IfcConversionBasedUnit"):
                        name = str(u.Name) if getattr(u, "Name", None) else "ConversionBased"
                        kind = "ConversionBased"
                    elif u.is_a("IfcDerivedUnit"):
                        name = str(getattr(u, "UserDefinedType", None)) if getattr(u, "UserDefinedType", None) else "Derived"
                        kind = "Derived"
                        elements = getattr(u, "Elements", None)
                        if elements:
                            elements_count = len(elements)
                    units_list.append({
                        "unit_type": unit_type,
                        "name": name,
                        "prefix": prefix,
                        "kind": kind,
                        "elements_count": elements_count
                    })
            if ua and units_list:
                for entry in units_list:
                    if entry["unit_type"] == "LENGTHUNIT":
                        length_unit_name = (entry["prefix"] + " " + entry["name"]).strip() if entry["prefix"] else entry["name"]
                        break
        except Exception:
            pass
        return {
            "length_unit": length_unit_name,
            "length_scale": scale,
            "schema": ifc_file.schema,
            "units": units_list if 'units_list' in locals() else []
        }

    def check(self, inputs: Dict[str, Any]) -> bool:
        p = inputs.get("ifc_path")
        return p and os.path.exists(p)
