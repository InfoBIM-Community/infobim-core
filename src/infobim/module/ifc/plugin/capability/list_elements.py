
import ifcopenshell
import ifcopenshell.util.element
from typing import Any, Dict, Optional
from ontobdc.run.core.port.contex import CliContextPort
from ontobdc.run.core.capability import Capability, CapabilityMetadata
from infobim.module.ifc.adapter.renderer.file_list import IfcElementsListRenderer
from infobim.module.ifc.util.element import get_basic_properties, get_element_text_value_or_default, get_material_name


class ListIfcElementsCapability(Capability):
    """
    Capability to list generic IFC elements by Class.
    Adapted from scripts/list_elements.py
    """
    METADATA = CapabilityMetadata(
        id="org.infobim.domain.ifc.capability.list_elements",
        version="0.1.0",
        name="List IFC Elements",
        description="Lists all elements of a specific IFC class from an IFC file.",
        author=["Elias M. P. Junior"],
        tags=["ifc", "bim", "elements", "list"],
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
                "ifc_class": {
                    "type": "string",
                    "uri": "org.infobim.domain.ifc.input.class",
                    "required": False,
                    "default": "IfcProduct",
                    "description": "IFC Class to list (e.g. IfcWall, IfcWindow).",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.infobim.domain.ifc.element.list.content": {
                    "type": "array",
                    "description": "List of element properties (dict)",
                },
                "org.infobim.domain.ifc.element.list.count": {
                    "type": "integer",
                    "description": "Number of elements found",
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
                "code": "org.infobim.domain.ifc.exception.invalid_class",
                "python_type": "ValueError",
                "description": "Invalid IFC Class",
            }
        ],
    )

    def get_default_cli_renderer(self) -> Optional[Any]:
        return IfcElementsListRenderer()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ifc_path = context.get_parameter_value("ifc_path")
        # Ensure we prioritize user input over default, handling both hyphen and underscore keys
        ifc_class = context.get_parameter_value("ifc_class") or "IfcProduct"

        try:
            # Open the IFC file using IfcOpenShell
            ifc_file = ifcopenshell.open(ifc_path)
        except Exception as e:
            raise RuntimeError(f"Error opening file: {e}")
        
        try:
            # 'by_type' returns all instances of the specified class (and subclasses).
            elements = ifc_file.by_type(ifc_class)
        except:
            raise ValueError(f"Invalid IFC Class: {ifc_class}")
        
        data = []
        for el in elements:
            # 1. Basic Props
            row = get_basic_properties(el)

            # 2. Material
            row["Material"] = get_material_name(el)

            # 3. Class specific info (e.g. PredefinedType)
            row["PredefinedType"] = get_element_text_value_or_default("PredefinedType", el)

            data.append(row)

        # Sort by Name
        data.sort(key=lambda x: x.get("Name", ""))

        return {
            "org.infobim.domain.ifc.element.list.content": data,
            "org.infobim.domain.ifc.element.list.count": len(data),
        }
