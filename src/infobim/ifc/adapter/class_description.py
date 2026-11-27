from typing import Any, Dict, List, Optional, Tuple

from infobim.ifc.adapter.ifc_datatype import IfcDatatype


class IfcClassDescription:
    """
    What the IFC schema says about a class: the attributes it has, each with its type and the class that declares it,
    and the property sets and quantity sets that apply to it (the templates the buildingSMART standard publishes), each
    with its properties. It needs no model: it is read from the schema and from the templates of ``ifcopenshell``.
    """

    @classmethod
    def read(cls, ifc_class: str, schema: str) -> Dict[str, Any]:
        """
        Raises:
            LookupError: the schema or the class is not known.
        """
        import ifcopenshell
        import ifcopenshell.util.pset

        try:
            declaration: Any = ifcopenshell.schema_by_name(schema).declaration_by_name(ifc_class)
        except RuntimeError as error:
            raise LookupError(f"{ifc_class} is not an entity of the schema {schema}: {error}") from error
        entity: Optional[Any] = declaration.as_entity()
        if entity is None:
            raise LookupError(f"{declaration.name()} is not an entity of the schema {schema}.")

        templates: Any = ifcopenshell.util.pset.PsetQto(schema)
        quantity_sets: List[str] = [template.Name for template in templates.get_applicable(entity.name(), qto_only=True)]
        return {
            "ifc_class": entity.name(),
            "schema": schema,
            "superclasses": cls._superclasses(entity),
            "attributes": cls._attributes(entity),
            "property_sets": [
                cls._property_set(template, template.Name in quantity_sets, schema)
                for template in templates.get_applicable(entity.name())
            ],
        }

    @staticmethod
    def _superclasses(entity: Any) -> List[str]:
        names: List[str] = []
        parent: Any = entity.supertype()
        while parent is not None:
            names.append(parent.name())
            parent = parent.supertype()
        return names

    @classmethod
    def _attributes(cls, entity: Any) -> List[Dict[str, Any]]:
        """Every attribute of the class, the inherited ones included, in the order of the schema."""
        declared_in: Dict[str, str] = {}
        parent: Any = entity
        while parent is not None:
            for attribute in parent.attributes():
                declared_in.setdefault(attribute.name(), parent.name())
            parent = parent.supertype()

        derived: List[bool] = list(entity.derived())
        attributes: List[Dict[str, Any]] = []
        for index, attribute in enumerate(entity.all_attributes()):
            attributes.append({
                "name": attribute.name(),
                "declared_in": declared_in[attribute.name()],
                "optional": attribute.optional(),
                "derived": derived[index],
                **cls._kind(attribute.type_of_attribute()),
            })
        return attributes

    @classmethod
    def _kind(cls, kind: Any) -> Dict[str, Any]:
        """How an attribute is typed: the type, what kind of type it is, and the values of an enumeration."""
        from ifcopenshell import ifcopenshell_wrapper as schema

        if isinstance(kind, schema.simple_type):
            return {"type": kind.declared_type(), "kind": "simple"}
        if isinstance(kind, schema.aggregation_type):
            return {"type": f"{kind.type_of_aggregation_string()} of {cls._kind(kind.type_of_element())['type']}", "kind": "aggregation"}
        if isinstance(kind, schema.named_type):
            declared: Any = kind.declared_type()
            if isinstance(declared, schema.enumeration_type):
                return {"type": declared.name(), "kind": "enumeration", "values": list(declared.enumeration_items())}
            if isinstance(declared, schema.type_declaration):
                return {"type": declared.name(), "kind": "type"}
            if isinstance(declared, schema.select_type):
                return {"type": declared.name(), "kind": "select"}
            return {"type": declared.name(), "kind": "entity"}
        raise TypeError(f"The attribute has a kind of type nobody knows: {kind!r}.")

    @classmethod
    def _property_set(cls, template: Any, is_quantity_set: bool, schema: str) -> Dict[str, Any]:
        return {
            "name": template.Name,
            "kind": "quantity_set" if is_quantity_set else "property_set",
            "description": template.Description or "",
            "applicable_to": template.ApplicableEntity or "",
            "properties": [cls._property(item, schema) for item in template.HasPropertyTemplates or []],
        }

    @classmethod
    def _property(cls, template: Any, schema: str) -> Dict[str, Any]:
        """A property of a set: its name, its kind (single value, enumerated, quantity…), its measure and its text."""
        values: List[str] = []
        if template.is_a("IfcSimplePropertyTemplate") and template.Enumerators:
            values = [str(getattr(value, "wrappedValue", value)) for value in template.Enumerators.EnumerationValues]
        measure: Any = template.PrimaryMeasureType if template.is_a("IfcSimplePropertyTemplate") else None
        datatype, editable = cls._editing(template, schema)
        return {
            "name": template.Name,
            "template_type": template.TemplateType,
            "measure": measure or "",
            "datatype": datatype,
            "editable": editable,
            "description": template.Description or "",
            "values": values,
            "properties": [cls._property(item, schema) for item in template.HasPropertyTemplates or []] if template.is_a("IfcComplexPropertyTemplate") else [],
        }

    @staticmethod
    def _editing(template: Any, schema: str) -> Tuple[str, bool]:
        """
        The datatype a property is edited as and whether it can be edited: a single value, an enumerated one and a
        quantity can; a bounded, listed, tabulated or referenced value, and a complex property, are structures.
        """
        if not template.is_a("IfcSimplePropertyTemplate"):
            return IfcDatatype.STRING, False
        quantity: Optional[str] = IfcDatatype.of_quantity(template.TemplateType)
        if quantity is not None:
            return quantity, True
        if template.TemplateType == "P_SINGLEVALUE" and template.PrimaryMeasureType:
            return IfcDatatype.of_type(schema, template.PrimaryMeasureType), True
        if template.TemplateType == "P_ENUMERATEDVALUE":
            return IfcDatatype.STRING, True
        return IfcDatatype.STRING, False
