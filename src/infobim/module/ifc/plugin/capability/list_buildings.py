
import os
import ifcopenshell
import ifcopenshell.util.element
from typing import Any, Dict, Optional
from ontobdc.run.core.port.contex import CliContextPort
from ontobdc.run.core.capability import Capability, CapabilityMetadata
from infobim.module.ifc.adapter.renderer.building_list import IfcBuildingListRenderer
from infobim.module.ifc.util.element import get_basic_properties


class ListIfcBuildingsCapability(Capability):
    """
    Capability to list IfcBuildings and their IfcBuildingStoreys.
    """
    METADATA = CapabilityMetadata(
        id="org.infobim.domain.ifc.capability.list_buildings",
        version="0.1.0",
        name="List IFC Buildings",
        description="Lists all Buildings and their Storeys.",
        author=["Elias M. P. Junior"],
        tags=["ifc", "bim", "building", "storey", "list"],
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
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.infobim.domain.ifc.building.list.content": {
                    "type": "array",
                    "description": "List of Buildings",
                },
                "org.infobim.domain.ifc.building.list.count": {
                    "type": "integer",
                    "description": "Number of Buildings found",
                },
            },
        },
        raises=[
            {
                "code": "org.infobim.domain.ifc.exception.file_not_found",
                "python_type": "FileNotFoundError",
                "description": "IFC file not found",
            },
        ],
    )

    def get_default_cli_renderer(self) -> Optional[Any]:
        return IfcBuildingListRenderer()

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ifc_path = context.get_parameter_value("ifc_path")

        if not os.path.exists(ifc_path):
            raise FileNotFoundError(f"File {ifc_path} not found.")

        try:
            ifc_file = ifcopenshell.open(ifc_path)
        except Exception as e:
            raise RuntimeError(f"Error opening file: {e}")
        
        buildings = ifc_file.by_type("IfcBuilding")
        result_data = []
        
        for building in buildings:
            building_data = get_basic_properties(building)
            
            # Find storeys related to this building
            # IfcBuilding -> IfcRelAggregates -> IfcBuildingStorey
            storeys = []
            if hasattr(building, "IsDecomposedBy"):
                for rel in building.IsDecomposedBy:
                     if rel.is_a("IfcRelAggregates"):
                         for obj in rel.RelatedObjects:
                             if obj.is_a("IfcBuildingStorey"):
                                 storey_data = get_basic_properties(obj)
                                 # Add elevation if available
                                 storey_data["Elevation"] = obj.Elevation if hasattr(obj, "Elevation") else "N/A"
                                 storeys.append(storey_data)
            
            # Sort storeys by Elevation descending (highest first)
            try:
                storeys.sort(key=lambda x: float(x.get("Elevation", 0)) if x.get("Elevation") != "N/A" else 0, reverse=True)
            except:
                storeys.sort(key=lambda x: x.get("Name", ""))

            # Format Elevation
            for s in storeys:
                elev = s.get("Elevation")
                if elev != "N/A":
                    try:
                        s["Elevation"] = f"{float(elev):.2f}"
                    except:
                        pass

            building_data["Storeys"] = storeys
            result_data.append(building_data)

        # Sort buildings by Name
        result_data.sort(key=lambda x: x.get("Name", ""))

        return {
            "org.infobim.domain.ifc.building.list.content": result_data,
            "org.infobim.domain.ifc.building.list.count": len(result_data),
        }
