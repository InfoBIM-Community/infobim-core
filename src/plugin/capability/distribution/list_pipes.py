
import os
import math
import numpy as np
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
from typing import Dict, Any, Tuple, Optional
from stack.src.bib.core.capability import Capability, CapabilityMetadata
from stack.src.bib.adapter.capability.cli.list_pipes import ListPipesCliStrategy as ListPipesCliStrategyAdapter
from stack.src.plugin.capability.distribution.nbr8160_uhc_sizing import UHCSizingCapability
from stack.src.plugin.capability.base.list_project_units import ProjectUnitsCapability


DOCS = """
# List Pipes Capability

Extracts and lists pipe segments with their geometric and property data.

## Features

- **Multi-Schema Support**: Works with both IFC4 (`IfcPipeSegment`) and IFC2X3 (`IfcFlowSegment`).
- **Smart DN Extraction**: Automatically detects units (meters vs mm) for Nominal Diameter.
- **Geometry Parsing**: Calculates true length and start/end elevations (Z) from local placement or axis representation.
- **Material Resolution**: Resolves material names from associations.

## Outputs

- `pipes`: List of dictionaries containing `guid`, `name`, `dn`, `material`, `z_start`, `z_end`, `length`.
- `count`: Total number of pipes found.
"""

class ListPipesCapability(Capability):

    METADATA = CapabilityMetadata(
        id="org.infobim.base.capability.list_pipes",
        version="0.1.0",
        name="List Pipes",
        description="Extracts and lists pipe segments with their geometric and property data (DN, Length, Z).",
        documentation=DOCS,
        author="Elias M. P. Junior",
        tags=["ifc", "pipes", "extraction", "reporting"],
        supported_languages=["en", "pt_BR"],
        supported_ifc_formats=["IFC2X3", "IFC4"],
        events={
            "success": [
                "org.infobim.base.capability.list_pipes.empty",
                "org.infobim.base.capability.list_pipes.all",
                "org.infobim.base.capability.list_pipes.many",
                "org.infobim.base.capability.list_pipes.paginated"
            ],
            "failure": [
                "org.infobim.base.capability.list_pipes.error"
            ]
        },
        request=[
            {
                "id": "org.infobim.base.capability.list_material",
                "type": "collection",
                "description": "Whether to list materials for each pipe",
                "condition": "materials",
                "fields": [
                    "GlobalId",
                    "Name"
                ]
            },
            {
                "id": "org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc",
                "type": "process",
                "description": "Calculate pipe sizing using UHC method",
                "condition": "uhc-sizing-suggest",
                "fields": []
            }
        ],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_path": {
                    "type": "string",
                    "required": True,
                    "description": "Absolute path to the IFC file"
                },
                "materials": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include material information"
                },
                "uhc-sizing-suggest": {
                    "type": "boolean",
                    "default": False,
                    "description": "Suggest pipe sizing using UHC method"
                },
                "org.ontobdc.common.lang.code": {
                    "type": "string",
                    "enum": ["en", "pt_BR"],
                    "default": "en",
                    "description": "Language for output messages and columns"
                }
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "org.ontobdc.aeco.distribution.flow.pipe.list.count": {
                    "type": "integer",
                    "description": "Total number of pipes found"
                },
                "org.ontobdc.aeco.distribution.flow.pipe.list": {
                    "type": "collection",
                    "items": {
                        "type": "object",
                        "properties": {
                            "guid": {"type": "string", "description": "Unique identifier for the pipe"},
                            "name": {"type": "string", "description": "Name of the pipe"},
                            "dn": {"type": "number", "description": "Nominal diameter of the pipe"},
                            "material": {"type": "string", "description": "Material of the pipe"},
                            "z_start": {"type": "number", "description": "Start elevation of the pipe"},
                            "z_end": {"type": "number", "description": "End elevation of the pipe"},
                            "length": {"type": "number", "description": "Length of the pipe segment"}
                        }
                    }
                }
            }
        }
    )

    @property
    def supports_global_id(self) -> bool:
        """Indicates if this capability supports returning GlobalId."""
        return True

    def get_default_cli_strategy(self, **kwargs) -> Optional[Any]:
        return ListPipesCliStrategyAdapter(**kwargs)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the pipe listing logic.

        Args:
            inputs: Dict containing:
                - ifc_path (str): Path to the IFC file.

        Returns:
            Dict containing:
                - org.ontobdc.aeco.distribution.flow.pipe.list.count (int): Number of pipes found.
                - org.ontobdc.aeco.distribution.flow.pipe.list (List[Dict]): List of extracted pipe data.
        """
        # Input validation handled by check() lifecycle method
        ifc_path = inputs.get("ifc_path")
        
        ifc_file = ifcopenshell.open(ifc_path)
        units_cap = ProjectUnitsCapability()
        units_out = units_cap.execute({"ifc_path": ifc_path})
        unit_scale = units_out.get("length_scale", 1.0)
        
        # Support both IFC4 and IFC2X3
        if ifc_file.schema == "IFC2X3":
            pipes = ifc_file.by_type("IfcFlowSegment")
        else:
            pipes = ifc_file.by_type("IfcPipeSegment")
            
        data = []
        
        for pipe in pipes:
            item_data = self._process_pipe(pipe, unit_scale)
            if item_data:
                data.append(item_data)
            
        # Sort: DN Desc, Name Asc
        data.sort(key=lambda x: (-x.get("dn", 0), x.get("name", "")))
        
        result = {
            "org.ontobdc.aeco.distribution.flow.pipe.list.count": len(data),
            "org.ontobdc.aeco.distribution.flow.pipe.list": data
        }
        if inputs.get("uhc-sizing-suggest"):
            uhc = UHCSizingCapability()
            sizing_out = uhc.execute({"pipes": data, "ifc_path": ifc_path})
            result["org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggestions"] = sizing_out.get("sized_pipes", [])
            result["events"] = ["org.ontobdc.aeco.distribution.flow.pipe.sizing.uhc.suggested"]
        return result

    def check(self, inputs: Dict[str, Any]) -> bool:
        """
        Checks if the inputs are valid for this capability.

        Args:
            inputs: Dict containing:
                - ifc_path (str): Path to the IFC file.

        Returns:
            bool: True if inputs are valid, False otherwise.
        """
        # Call base check for language validation
        try:
            super().check(inputs)
        except ValueError as e:
            raise e

        ifc_path = inputs.get("ifc_path")
        return ifc_path and os.path.exists(ifc_path)

    def validate(self, outputs: Dict[str, Any]) -> None:
        """
        Validates the outputs for this capability.
        
        Args:
            outputs: Dict containing:
                - org.ontobdc.aeco.distribution.flow.pipe.list.count (int): Number of pipes found.
                - org.ontobdc.aeco.distribution.flow.pipe.list (List[Dict]): List of extracted pipe data.
                
        Raises:
            ValueError: If outputs are invalid.
        """
        if not outputs or "org.ontobdc.aeco.distribution.flow.pipe.list.count" not in outputs or "org.ontobdc.aeco.distribution.flow.pipe.list" not in outputs:
            raise ValueError("Invalid outputs for ListPipesCapability.")
        
        pipes = outputs["org.ontobdc.aeco.distribution.flow.pipe.list"]
        count = outputs["org.ontobdc.aeco.distribution.flow.pipe.list.count"]
        
        if count != len(pipes):
            raise ValueError(f"Mismatch between count ({count}) and number of pipes ({len(pipes)}).")

    def _process_pipe(self, pipe, unit_scale) -> Dict[str, Any]:
        """
        Process a single pipe element. Can be overridden by subclasses.
        """
        name = pipe.Name if pipe.Name else "Unnamed"
        
        # Psets
        psets = ifcopenshell.util.element.get_psets(pipe)
        
        # 1. DN
        dn = 0.0
        
        # Check common Psets for NominalDiameter (IFC4 vs IFC2X3)
        dn_val = None
        if "Pset_PipeSegmentTypeCommon" in psets and "NominalDiameter" in psets["Pset_PipeSegmentTypeCommon"]:
            dn_val = psets["Pset_PipeSegmentTypeCommon"]["NominalDiameter"]
        elif "Pset_PipeCommon" in psets and "NominalDiameter" in psets["Pset_PipeCommon"]:
            dn_val = psets["Pset_PipeCommon"]["NominalDiameter"] # IFC2X3 common
            
        if dn_val:
            dn_float = float(dn_val)
            # Heuristic: If < 5.0, assume meters and convert to mm
            if dn_float < 5.0: 
                dn = dn_float * 1000.0
            else:
                dn = dn_float
        
        # 2. Material
        material = "-"
        
        # 3. Geometry
        length, z_start, z_end = self._get_geometry_info(pipe)
        
        # Adjust Length unit if necessary (display in meters)
        length_m = length * unit_scale
        
        # Adjust Z to meters
        z_start_m = z_start * unit_scale
        z_end_m = z_end * unit_scale
        
        return {
            "guid": pipe.GlobalId,
            "name": name,
            "dn": dn,
            "material": material,
            "z_start": z_start_m,
            "z_end": z_end_m,
            "length": length_m,
            "psets": psets # Pass psets for subclasses to use without re-extracting
        }



    def _get_geometry_info(self, element) -> Tuple[float, float, float]:
        """
        Returns length, start_z, end_z
        """
        # 1. Get Length (Quantity or BBox or Pset)
        length = 0.0
        psets = ifcopenshell.util.element.get_psets(element)
        if "Qto_DistributionElement" in psets and "Length" in psets["Qto_DistributionElement"]:
            length = float(psets["Qto_DistributionElement"]["Length"])
        
        # 2. Get Endpoints for Z
        start_z = 0.0
        end_z = 0.0
        
        try:
            m = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
            
            # 1. Try to find Axis representation
            axis_rep = None
            body_rep = None
            
            if element.Representation:
                for rep in element.Representation.Representations:
                    if rep.RepresentationIdentifier == "Axis":
                        axis_rep = rep
                    elif rep.RepresentationIdentifier == "Body":
                        body_rep = rep
            
            length_geom = 0.0
            z1 = 0.0
            z2 = 0.0
            found_geom = False
            
            if axis_rep and axis_rep.Items:
                item = axis_rep.Items[0]
                if item.is_a("IfcPolyline"):
                    points = item.Points
                    pt_start = points[0].Coordinates
                    pt_end = points[-1].Coordinates
                    
                    def to_3d(pt):
                        return list(pt) + [0.0]*(3-len(pt))
                    
                    v_start = to_3d(pt_start) + [1.0]
                    v_end = to_3d(pt_end) + [1.0]
                    
                    w_start = m @ np.array(v_start)
                    w_end = m @ np.array(v_end)
                    
                    z1 = w_start[2]
                    z2 = w_end[2]
                    length_geom = math.dist(w_start[:3], w_end[:3])
                    found_geom = True
                    
            if not found_geom and body_rep and body_rep.Items:
                item = body_rep.Items[0]
                if item.is_a("IfcExtrudedAreaSolid"):
                    placement = item.Position
                    depth = item.Depth
                    direction = item.ExtrudedDirection.DirectionRatios
                    
                    m_ext = ifcopenshell.util.placement.get_axis2placement(placement)
                    m_combined = m @ m_ext
                    
                    v_start = [0.0, 0.0, 0.0, 1.0]
                    w_start = m_combined @ np.array(v_start)
                    
                    d_vec = np.array(list(direction) + [0.0])
                    d_norm = np.linalg.norm(d_vec[:3])
                    if d_norm > 0:
                        d_vec = d_vec / d_norm
                    
                    rot_mat = m_combined[:3, :3]
                    d_world = rot_mat @ d_vec[:3]
                    
                    w_end_3 = w_start[:3] + d_world * depth
                    
                    z1 = w_start[2]
                    z2 = w_end_3[2]
                    length_geom = depth
                    found_geom = True

            if found_geom:
                if length == 0.0:
                    length = length_geom
                return length, z1, z2
            
            z1 = m[2, 3]
            return length, z1, 0.0
                    
        except Exception as e:
            print(f"Error processing geometry for {element.GlobalId}: {e}")
            pass
        
        return length, 0.0, 0.0
