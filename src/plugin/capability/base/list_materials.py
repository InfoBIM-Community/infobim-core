
import os
import ifcopenshell
import ifcopenshell.util.element
from typing import Dict, Any, List, Optional
from stack.src.bib.core.capability import Capability, CapabilityMetadata
from stack.src.bib.core.capability.cli_strategy import CapabilityCliStrategy
from stack.src.bib.adapter.capability.cli.list_materials import ListMaterialsCliStrategy as ListMaterialsCliStrategyAdapter
from stack.src.bib.core.capability.executor import CapabilityExecutor
from rich.console import Console
import argparse
import json


class ListMaterialsCapability(Capability):
    """
    Capability to list materials from an IFC file.
    Can return a mapping of Element GlobalId -> Material Name.
    """
    
    METADATA = CapabilityMetadata(
        id="org.infobim.base.capability.list_material",
        version="0.1.0",
        name="List Materials",
        description="Lists materials associated with elements in an IFC file.",
        author="InfoBIM",
        tags=["ifc", "materials", "extraction"],
        supported_languages=["en", "pt_BR"],
        supported_ifc_formats=["IFC2X3", "IFC4"],
        events={
            "success": [
                "org.infobim.base.capability.list_material.empty",
                "org.infobim.base.capability.list_material.all",
                "org.infobim.base.capability.list_material.many",
                "org.infobim.base.capability.list_material.paginated"
            ],
            "failure": ["org.infobim.base.capability.list_material.error"]
        },
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "required": True,
                    "description": "Absolute path to the IFC file"
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of fields to retrieve (e.g., GlobalId, Name)",
                    "default": ["GlobalId", "Name"]
                }
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.aeco.material.list.count": {
                    "type": "integer",
                    "description": "Total number of material associations found"
                },
                "org.ontobdc.aeco.material.list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "GlobalId": {"type": "string"},
                            "Material": {"type": "string"}
                        }
                    },
                    "description": "List of material associations"
                }
            }
        }
    )

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ifc_path = inputs.get("ifc_path")
        fields = inputs.get("fields", ["GlobalId", "Name"])
        
        ifc_file = ifcopenshell.open(ifc_path)
        
        # Strategy: Find all IfcRelAssociatesMaterial
        associations = ifc_file.by_type("IfcRelAssociatesMaterial")
        
        data = []
        
        for rel in associations:
            material_name = self._get_material_name_from_rel(rel)
            if not material_name:
                continue
                
            # Each relationship can apply to multiple objects
            for obj in rel.RelatedObjects:
                if hasattr(obj, "GlobalId"):
                    entry = {"Material": material_name}
                    if "GlobalId" in fields:
                        entry["GlobalId"] = obj.GlobalId
                    if "Name" in fields and hasattr(obj, "Name"):
                        entry["Name"] = obj.Name
                        
                    data.append(entry)
                    
        return {
            "org.ontobdc.aeco.material.list.count": len(data),
            "org.ontobdc.aeco.material.list": data
        }

    def _get_material_name_from_rel(self, rel) -> str:
        mat = rel.RelatingMaterial
        if not mat:
            return "Unknown"
            
        if mat.is_a("IfcMaterial"):
            return mat.Name
        elif mat.is_a("IfcMaterialLayerSetUsage"):
            # Simplify for now, just say LayerSet or try to get first layer
            return "LayerSet"
        elif mat.is_a("IfcMaterialList"):
             if mat.Materials:
                 return mat.Materials[0].Name # Return first material
             return "MaterialList"
        return "Unknown"

    def check(self, inputs: Dict[str, Any]) -> bool:
        path = inputs.get("ifc_path")
        if not path or not os.path.exists(path):
            return False
        return True

    def get_default_cli_strategy(self, **kwargs) -> Optional[Any]:
        return ListMaterialsCliStrategyAdapter(**kwargs)

 
