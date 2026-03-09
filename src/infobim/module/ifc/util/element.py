
import ifcopenshell
import ifcopenshell.util.element
from typing import Any, Dict, Optional
from infobim.module.ifc.util.number import round_and_format


def get_element_text_value_or_default(key: str, element: Any, default: str = None) -> str:
    """
    Returns the value of the element property if it exists, otherwise returns the default value.
    """
    # 1. Get raw value
    raw_value = getattr(element, key, None)
    
    # 2. Check if raw value is None
    if raw_value is None:
            val_str = None
    else:
            val_str = str(raw_value).strip()

    # 3. Check for "None" string or empty
    if val_str == "None" or val_str == "":
        val_str = None
        
    # 4. Return valid value or default/fallback
    if val_str:
        return val_str
        
    if default:
        return default
        
    return "-" if key in ["Name", "Description", "PredefinedType"] else "N/A"

def get_basic_properties(element) -> Dict[str, Any]:
    """
    Extracts basic properties like Name, Description, Tag, ObjectType.
    """
    props = {
        "GlobalId": get_element_text_value_or_default("GlobalId", element),
        "Name": get_element_text_value_or_default("Name", element),
        "Description": get_element_text_value_or_default("Description", element),
        "ObjectType": get_element_text_value_or_default("ObjectType", element),
        "Tag": get_element_text_value_or_default("Tag", element),
        "Class": element.is_a()
    }

    return props

def get_material_name(element) -> str:
    """
    Retrieves the material name associated with the element.
    """
    mat = ifcopenshell.util.element.get_material(element)
    if not mat:
        return "-"
    if mat.is_a("IfcMaterial"):
        return mat.Name
    if mat.is_a("IfcMaterialList"):
        return ", ".join([m.Name for m in mat.Materials])
    if mat.is_a("IfcMaterialLayerSetUsage"):
        if mat.ForLayerSet and mat.ForLayerSet.MaterialLayers:
                return ", ".join([l.Material.Name for l in mat.ForLayerSet.MaterialLayers if l.Material])
    if mat.is_a("IfcMaterialProfileSetUsage"):
        if mat.ForProfileSet and mat.ForProfileSet.MaterialProfiles:
                return ", ".join([p.Material.Name for p in mat.ForProfileSet.MaterialProfiles if p.Material])
    return "-"

def get_attribute_value(element, attribute_name: str) -> Optional[Any]:
    """
    Retrieves the value of a specific attribute from the element.
    """
    return getattr(element, attribute_name, None)

def get_all_attributes(element) -> Dict[str, Dict[str, Any]]:
    """
    Retrieves all attributes of the element, grouped by their defining class hierarchy up to IfcRoot.
    """
    result = {}
    
    # Get the inheritance hierarchy
    current_entity = element
    hierarchy = []
    
    # Using IfcOpenShell entity definition to traverse hierarchy
    # element.wrapped_data.is_a() returns the class name.
    # We can inspect the schema to get parent classes.
    schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(element.file.schema)
    entity_def = schema.declaration_by_name(element.is_a())
    
    while entity_def:
        hierarchy.append(entity_def)
        entity_def = entity_def.supertype()

    # Reverse hierarchy to start from IfcRoot (or top-most parent)
    hierarchy.reverse()

    for entity_def in hierarchy:
        class_name = entity_def.name()

        attribute_count = entity_def.attribute_count()
        for i in range(attribute_count):
            attr_def = entity_def.attribute_by_index(i)
            attr_name = attr_def.name()
    
    # Re-build hierarchy list (Specific -> Root)
    hierarchy_defs = []
    e_def = schema.declaration_by_name(element.is_a())
    while e_def:
        hierarchy_defs.append(e_def)
        e_def = e_def.supertype()
        
    # Now iterate from top (Root) down to Specific
    hierarchy_defs.reverse() 
    
    previous_attrs = set()
    result = {} # Ordered dict by default in Python 3.7+

    for e_def in hierarchy_defs:
        class_name = e_def.name()
        current_attrs = set()
        
        count = e_def.attribute_count()
        for i in range(count):
            current_attrs.add(e_def.attribute_by_index(i).name())
            
        # Attributes defined in THIS class are (Current - Previous)
        defined_attrs_names = current_attrs - previous_attrs
        
        class_data = {}
        for attr_name in defined_attrs_names:
            # Retrieve value from the element instance
            val = getattr(element, attr_name, None)

            # Format value
            if val is None:
                val_str = None
            elif isinstance(val, (tuple, list)):
                 val_str = str(val)
            elif isinstance(val, float):
                 val_str = round_and_format(val)
            elif attr_name == "ObjectPlacement":
                 val_str = format_local_placement(val)
            elif hasattr(val, "is_a"):
                 val_str = f"#{val.id()} {val.is_a()}"
            else:
                 val_str = str(val)

            class_data[attr_name] = val_str
            
        if class_data:
            # Exclude specific attributes as requested
            if class_name == "IfcRoot" and attr_name == "OwnerHistory":
                continue
            if class_name == "IfcProduct" and attr_name == "ObjectPlacement":
                continue

            result[class_name] = class_data
        else:
            result[class_name] = None
            
        previous_attrs = current_attrs

    return result

def format_local_placement(placement) -> Optional[Any]:
    """
    Extracts local placement information into a dictionary/JSON structure.
    Returns:
        {
            "Location": [x, y, z],
            "Axis": [x, y, z],
            "RefDirection": [x, y, z]
        }
    Or fallback to "#{id} {class}" if extraction fails.
    """
    if placement is None:
        return None

    try:
        data = {"Location": None, "Axis": None, "RefDirection": None}
        
        # Check for RelativePlacement (IfcAxis2Placement3D or IfcAxis2Placement2D)
        if hasattr(placement, "RelativePlacement") and placement.RelativePlacement:
            rel_placement = placement.RelativePlacement
            
            # Location (Point)
            if hasattr(rel_placement, "Location") and rel_placement.Location:
                coords = rel_placement.Location.Coordinates
                # Round coordinates
                data["Location"] = [round_and_format(c) for c in coords]
                
            # Axis (Z Direction) - 3D only
            if hasattr(rel_placement, "Axis") and rel_placement.Axis:
                axis = rel_placement.Axis.DirectionRatios
                data["Axis"] = [round_and_format(c) for c in axis]
                
            # RefDirection (X Direction) - 3D and 2D
            if hasattr(rel_placement, "RefDirection") and rel_placement.RefDirection:
                ref = rel_placement.RefDirection.DirectionRatios
                data["RefDirection"] = [round_and_format(c) for c in ref]
                
        if data:
            return data
            
    except Exception:
        pass
        
    # Fallback
    if hasattr(placement, "is_a"):
         return f"#{placement.id()} {placement.is_a()}"
         
    return str(placement)
