
import os
import ifcopenshell
import ifcopenshell.util.element
from typing import Any, Dict, Optional
from ontobdc.run.core.port.contex import CliContextPort
from ontobdc.run.core.capability import Capability, CapabilityMetadata
from infobim.module.ifc.adapter.renderer.property_set_list import IfcPropertySetListRenderer


class ListIfcPropertySetsCapability(Capability):
    """
    Capability to list Property Sets and their properties for a specific IFC element.
    """
    METADATA = CapabilityMetadata(
        id="org.infobim.domain.ifc.capability.list_property_sets",
        version="0.1.0",
        name="List IFC Property Sets",
        description="Lists all Property Sets and properties of a specific element.",
        author=["Elias M. P. Junior"],
        tags=["ifc", "bim", "properties", "pset", "list"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "uri": "org.infobim.domain.ifc.input.path",
                    "required": True,
                    "description": "Path to the IFC file.",
                },
                "global_id": {
                    "type": "string",
                    "uri": "org.infobim.domain.ifc.input.element.id",
                    "required": True,
                    "description": "GlobalId (22 chars) or StepId (integer) of the element.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.infobim.domain.ifc.pset.list.content": {
                    "type": "array",
                    "description": "List of Property Sets",
                },
                "org.infobim.domain.ifc.pset.list.count": {
                    "type": "integer",
                    "description": "Number of Property Sets found",
                },
            },
        },
        raises=[
            {
                "code": "org.infobim.domain.ifc.exception.file_not_found",
                "python_type": "FileNotFoundError",
                "description": "IFC file not found",
            },
            {
                "code": "org.infobim.domain.ifc.exception.element_not_found",
                "python_type": "ValueError",
                "description": "Element not found",
            }
        ],
    )

    def get_default_cli_renderer(self) -> Optional[Any]:
        return IfcPropertySetListRenderer()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ifc_path = context.get_parameter_value("ifc_path")
        global_id = context.get_parameter_value("global_id")

        if not os.path.exists(ifc_path):
            raise FileNotFoundError(f"File {ifc_path} not found.")

        try:
            ifc_file = ifcopenshell.open(ifc_path)
        except Exception as e:
            raise RuntimeError(f"Error opening file: {e}")
        
        element = None
        # Try to find element by GlobalId (22 chars) or StepId
        if len(str(global_id)) == 22:
            try:
                element = ifc_file.by_guid(global_id)
            except:
                pass
        
        if not element and str(global_id).isdigit():
            try:
                element = ifc_file.by_id(int(global_id))
            except:
                pass
                
        if not element:
             # Fallback: try to iterate if not found by direct lookup (rare but possible if ID format is weird)
             pass

        if not element:
            raise ValueError(f"Element with ID '{global_id}' not found in {ifc_path}.")

        # Get Property Sets using ifcopenshell utility
        # This returns a dict: { "Pset_Name": { "PropName": Value, ... }, ... }
        psets_dict = ifcopenshell.util.element.get_psets(element)
        
        result_data = []
        
        for pset_name, props in psets_dict.items():
            # Skip empty psets if any
            if not props:
                continue
                
            prop_list = []
            for prop_name, prop_val in props.items():
                # Determine a simple type string
                val_type = type(prop_val).__name__
                if prop_val is None:
                    val_str = "None"
                elif isinstance(prop_val, bool):
                    val_str = prop_val
                elif isinstance(prop_val, int):
                    val_str = int(prop_val)
                elif isinstance(prop_val, float):
                    val_str = float(prop_val)
                else:
                    val_str = str(prop_val)
                    
                prop_list.append({
                    "Name": prop_name,
                    "Value": val_str,
                    "Type": val_type
                })
            
            # Sort properties by name
            prop_list.sort(key=lambda x: x["Name"])
            
            result_data.append({
                "name": pset_name,
                "properties": prop_list
            })

        # Sort psets by name
        result_data.sort(key=lambda x: x["name"])

        return {
            "org.infobim.domain.ifc.pset.list.content": result_data,
            "org.infobim.domain.ifc.pset.list.count": len(result_data),
        }

# ifcopenshell.entity_instance
