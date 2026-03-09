from typing import Any, Dict, Optional
import os
import uuid
import ifcopenshell
import ifcopenshell.api
from ontobdc.run.core.action import Action, ActionMetadata
# from infobim.module.ifc.adapter.strategy.cli_extruded_element import CreateExtrudedElementCliStrategy


class CreateExtrudedElementAction(Action):
    """
    Action to create an extruded element (e.g., IfcBuildingElementProxy) at a specific position.
    Adapted from scripts/create_extruded_element.py
    """
    METADATA = ActionMetadata(
        id="org.infobim.domain.ifc.action.create_extruded_element",
        version="0.1.0",
        name="Create Extruded IFC Element",
        description="Creates a rectangular element extruded downwards in an IFC file.",
        author=["Elias M. P. Junior"],
        tags=["ifc", "bim", "geometry", "create"],
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc-path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the input IFC file.",
                },
                "output_path": {
                    "type": "string",
                    "required": False,
                    "description": "Path to save the modified IFC file. If not provided, overwrites input.",
                },
                "name": {
                    "type": "string",
                    "required": True,
                    "description": "Name of the element to create.",
                },
                "x": {
                    "type": "number",
                    "required": True,
                    "description": "X coordinate position.",
                },
                "y": {
                    "type": "number",
                    "required": True,
                    "description": "Y coordinate position.",
                },
                "depth": {
                    "type": "number",
                    "required": True,
                    "description": "Depth (thickness) of the extrusion.",
                },
                "width": {
                    "type": "number",
                    "required": True,
                    "description": "Width of the element.",
                },
                "length": {
                    "type": "number",
                    "required": True,
                    "description": "Length of the element.",
                },
                "ifc_class_name": {
                    "type": "string",
                    "required": False,
                    "default": "IfcBuildingElementProxy",
                    "description": "IFC Class of the element (e.g. IfcBuildingElementProxy, IfcSlab).",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "infobim.module.ifc.element.created.global_id": {
                    "type": "string",
                    "description": "GlobalId of the created element",
                },
                "infobim.module.ifc.file.path": {
                    "type": "string",
                    "description": "Path to the saved IFC file",
                },
            },
        },
        raises=[
            {
                "code": "infobim.module.ifc.exception.file_not_found",
                "python_type": "FileNotFoundError",
                "description": "Input IFC file not found",
            },
            {
                "code": "infobim.module.ifc.exception.creation_failed",
                "python_type": "RuntimeError",
                "description": "Failed to create element geometry or instance",
            }
        ],
    )

    def get_default_cli_strategy(self, **kwargs: Any) -> Optional[Any]:
        return CreateExtrudedElementCliStrategy(**kwargs)

    def _create_guid(self):
        """Generates a compressed GUID (Global Unique Identifier) required by IFC."""
        return ifcopenshell.guid.compress(uuid.uuid1().hex)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ifc_path = inputs.get("ifc-path")
        output_path = inputs.get("output_path") or ifc_path
        name = inputs.get("name")
        x = float(inputs.get("x"))
        y = float(inputs.get("y"))
        depth = float(inputs.get("depth"))
        width = float(inputs.get("width"))
        length = float(inputs.get("length"))
        ifc_class_name = inputs.get("ifc_class_name", "IfcBuildingElementProxy")

        if not os.path.exists(ifc_path):
            raise FileNotFoundError(f"Input file {ifc_path} not found.")

        try:
            ifc_file = ifcopenshell.open(ifc_path)
        except Exception as e:
            raise RuntimeError(f"Error opening file: {e}")

        # --- 1. Create Placement (Location and Orientation) ---
        pt = ifc_file.createIfcCartesianPoint((float(x), float(y), 0.0))
        axis = ifc_file.createIfcDirection((0.0, 0.0, 1.0))
        ref = ifc_file.createIfcDirection((1.0, 0.0, 0.0))
        axis2placement = ifc_file.createIfcAxis2Placement3D(pt, axis, ref)
        local_placement = ifc_file.createIfcLocalPlacement(None, axis2placement)

        # --- 2. Create Geometry (Body Representation) ---
        profile = ifc_file.createIfcRectangleProfileDef("AREA", None, None, float(width), float(length))
        extrusion_dir = ifc_file.createIfcDirection((0.0, 0.0, -1.0))
        solid_pos = ifc_file.createIfcAxis2Placement3D(ifc_file.createIfcCartesianPoint((0.0, 0.0, 0.0)))
        solid = ifc_file.createIfcExtrudedAreaSolid(profile, solid_pos, extrusion_dir, float(depth))

        context = None
        for ctx in ifc_file.by_type("IfcGeometricRepresentationContext"):
            if ctx.ContextType == "Model":
                context = ctx
                break
        if not context:
            if len(ifc_file.by_type("IfcGeometricRepresentationContext")) > 0:
                context = ifc_file.by_type("IfcGeometricRepresentationContext")[0]
            else:
                 raise RuntimeError("No IfcGeometricRepresentationContext found in file.")

        rep = ifc_file.createIfcShapeRepresentation(context, "Body", "SweptSolid", [solid])
        product_def_shape = ifc_file.createIfcProductDefinitionShape(None, None, [rep])

        # --- 3. Create Element Instance ---
        try:
            element = ifc_file.create_entity(
                ifc_class_name,
                GlobalId=self._create_guid(), 
                Name=name,
                ObjectPlacement=local_placement,
                Representation=product_def_shape
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create class '{ifc_class_name}'. Error: {e}")

        if not hasattr(element, "Representation"):
             raise RuntimeError(f"Class '{ifc_class_name}' does not support geometry (no Representation attribute).")

        # --- 4. Add to Spatial Structure ---
        structure = None
        storeys = ifc_file.by_type("IfcBuildingStorey")
        if storeys:
            structure = storeys[0]
        else:
            sites = ifc_file.by_type("IfcSite")
            if sites:
                structure = sites[0]
            else:
                projs = ifc_file.by_type("IfcProject")
                if projs:
                    structure = projs[0]

        if structure:
            rel = None
            for r in ifc_file.by_type("IfcRelContainedInSpatialStructure"):
                if r.RelatingStructure == structure:
                    rel = r
                    break
            
            if rel:
                rel.RelatedElements = list(rel.RelatedElements) + [element]
            else:
                ifc_file.createIfcRelContainedInSpatialStructure(self._create_guid(), None, "Building Storey Container", None, [element], structure)

        ifc_file.write(output_path)

        return {
            "infobim.module.ifc.element.created.global_id": element.GlobalId,
            "infobim.module.ifc.file.path": output_path
        }
