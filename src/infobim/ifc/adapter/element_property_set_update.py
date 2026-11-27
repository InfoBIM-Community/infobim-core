from typing import Any, Dict, List, Optional

from infobim.ifc.adapter.element_values import IfcValueText
from infobim.ifc.adapter.ifc_datatype import IfcDatatype


class IfcElementPropertySetUpdate:
    """
    Changes the properties of one property set, or one quantity set, of an IfcElement, and says which changed. The set is the
    one of the element itself: when the element has none of that name (it may have the one of its type) it gets one. A
    property takes the datatype the template of the standard gives it, else the one of the value it has, else text; a
    property that is a structure (a bounded, listed or tabulated value, a complex property) cannot be changed here.
    """

    @classmethod
    def apply(cls, element: Any, set_name: str, changes: Dict[str, str]) -> List[str]:
        """
        Raises:
            ValueError: a property cannot be changed, or its text is not a value of its datatype.
        """
        import ifcopenshell.api.pset
        import ifcopenshell.util.element
        import ifcopenshell.util.pset

        model: Any = element.file
        template: Optional[Any] = ifcopenshell.util.pset.PsetQto(model.schema).get_by_name(set_name)
        own: Optional[Any] = cls._own_set(element, set_name)
        is_quantity: bool = own.is_a("IfcElementQuantity") if own is not None else (
            template.TemplateType.startswith("QTO") if template is not None else set_name.startswith("Qto_")
        )
        current: Dict[str, Any] = ifcopenshell.util.element.get_psets(element).get(set_name, {})
        templates: Dict[str, Any] = {item.Name: item for item in (template.HasPropertyTemplates if template is not None else [])}

        properties: Dict[str, Any] = {}
        for name, text in changes.items():
            value: Any = IfcDatatype.convert(text, cls._datatype(set_name, name, templates.get(name), current.get(name), model.schema))
            if value != current.get(name):
                properties[name] = value
        if not properties:
            return []

        if own is None:
            own = (
                ifcopenshell.api.pset.add_qto(model, product=element, name=set_name)
                if is_quantity
                else ifcopenshell.api.pset.add_pset(model, product=element, name=set_name)
            )
        # The API takes the properties it applies out of the dictionary it is given: it is given a copy.
        if is_quantity:
            ifcopenshell.api.pset.edit_qto(model, qto=own, properties=dict(properties), pset_template=template)
        else:
            ifcopenshell.api.pset.edit_pset(model, pset=own, properties=dict(properties), pset_template=template)
        return sorted(properties)

    @staticmethod
    def _own_set(element: Any, set_name: str) -> Optional[Any]:
        """The property set or quantity set of that name the element itself has, none when it has none."""
        for relation in element.IsDefinedBy or []:
            if not relation.is_a("IfcRelDefinesByProperties"):
                continue
            definition: Any = relation.RelatingPropertyDefinition
            if definition.is_a() in ("IfcPropertySet", "IfcElementQuantity") and definition.Name == set_name:
                return definition
        return None

    @staticmethod
    def _datatype(set_name: str, name: str, template: Optional[Any], current: Any, schema: str) -> str:
        if template is not None:
            if not template.is_a("IfcSimplePropertyTemplate"):
                raise ValueError(f"The property {name} of {set_name} is a structure, and cannot be changed as text.")
            quantity: Optional[str] = IfcDatatype.of_quantity(template.TemplateType)
            if quantity is not None:
                return quantity
            if template.TemplateType == "P_SINGLEVALUE" and template.PrimaryMeasureType:
                return IfcDatatype.of_type(schema, template.PrimaryMeasureType)
            if template.TemplateType == "P_ENUMERATEDVALUE":
                return IfcDatatype.STRING
            raise ValueError(f"The property {name} of {set_name} is a structure, and cannot be changed as text.")
        if current is not None:
            if isinstance(current, (dict, list, tuple)):
                raise ValueError(f"The property {name} of {set_name} is a structure, and cannot be changed as text.")
            return IfcDatatype.of_value(current)
        return IfcDatatype.STRING

    @staticmethod
    def text_of(value: Any) -> str:
        return "".join(IfcValueText.of(value))
