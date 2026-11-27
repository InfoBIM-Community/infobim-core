from typing import Any, Dict, List

from infobim.ifc.adapter.element_values import IfcValueText


class IfcElementPropertySets:
    """
    The property sets of an IfcElement, and its quantity sets: each one with the properties it holds, the ones of the
    type of the element included. They are read from the element, so they depend on the model.
    """

    @classmethod
    def read(cls, element: Any) -> List[Dict[str, Any]]:
        """Each set, by its name, as ``{"name": …, "properties": [{"name": …, "values": […]}]}``."""
        import ifcopenshell.util.element

        sets: Dict[str, Dict[str, Any]] = ifcopenshell.util.element.get_psets(element)
        return [
            {
                "name": set_name,
                "properties": [
                    {"name": property_name, "values": IfcValueText.of(value)}
                    for property_name, value in sets[set_name].items()
                    if property_name != "id"
                ],
            }
            for set_name in sorted(sets)
        ]
