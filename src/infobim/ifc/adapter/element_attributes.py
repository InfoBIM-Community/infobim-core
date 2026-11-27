from typing import Any, ClassVar, Dict, List, Set

from infobim.ifc.adapter.element_values import IfcValueText
from infobim.ifc.adapter.ifc_datatype import IfcDatatype


class IfcElementAttributes:
    """
    What an IfcElement has beyond the fields every element shows: the attributes its own class declares in the IFC
    schema (the ``PredefinedType`` of an IfcWall, the ``OverallHeight`` of an IfcDoor). Which they are depends on the
    real class of the element, so they are read from the schema and from the element, and no facade has to declare
    them. Each one is a field the person can read and change: it says its datatype, and the values an enumeration takes.
    The property sets are not here: ``infobim ifc --pset`` lists them.
    """

    #: The attributes the fields of every element already show, by the field of the facade of IfcElement.
    SHOWN: ClassVar[Set[str]] = {"GlobalId", "Name", "Description", "ObjectType", "Tag"}

    @classmethod
    def fields(cls, element: Any) -> List[Dict[str, Any]]:
        """The fields of the attributes of the class of the element."""
        fields: List[Dict[str, Any]] = []
        for name, attribute in cls._editable(element).items():
            kind: Any = attribute.type_of_attribute()
            field: Dict[str, Any] = {
                "name": name,
                "editable": True,
                "datatype": IfcDatatype.of_kind(kind),
                "values": IfcValueText.of(getattr(element, name)),
            }
            options: List[str] = cls._options(kind)
            if options:
                field["options"] = options
            fields.append(field)
        return fields

    @classmethod
    def assign(cls, element: Any, name: str, text: str) -> None:
        """
        Gives the attribute the value the text is, as the datatype of the attribute; an empty text clears it.

        Raises:
            ValueError: the class of the element has no such attribute to change, or the text is not a value of it.
        """
        attribute: Any = cls._editable(element).get(name)
        if attribute is None:
            raise ValueError(f"The {element.is_a()} has no attribute {name} that can be changed.")

        kind: Any = attribute.type_of_attribute()
        options: List[str] = cls._options(kind)
        if options and text.strip() and text.strip().upper() not in options:
            raise ValueError(f"{text!r} is not a value of {name}: {', '.join(options)}.")

        value: Any = IfcDatatype.convert(text.strip().upper() if options else text, IfcDatatype.of_kind(kind))
        if value is None and not attribute.optional():
            raise ValueError(f"The attribute {name} is required.")
        setattr(element, name, value)

    @classmethod
    def names(cls, element: Any) -> Set[str]:
        """The names of the attributes of the class of the element a person can change."""
        return set(cls._editable(element))

    @classmethod
    def text_of(cls, element: Any, name: str) -> str:
        """The text the attribute holds now, as the entity shows it; empty when it holds none."""
        return "".join(IfcValueText.of(getattr(element, name)))

    @classmethod
    def _editable(cls, element: Any) -> Dict[str, Any]:
        """The attributes of the class of the element a person can change, by name: not the ones shown as facade fields."""
        import ifcopenshell

        declaration: Any = ifcopenshell.schema_by_name(element.file.schema_identifier).declaration_by_name(element.is_a()).as_entity()
        derived: List[bool] = list(declaration.derived())
        return {
            attribute.name(): attribute
            for index, attribute in enumerate(declaration.all_attributes())
            if attribute.name() not in cls.SHOWN and not derived[index] and cls._is_primitive(attribute.type_of_attribute())
        }

    @classmethod
    def _options(cls, kind: Any) -> List[str]:
        """The values an enumeration takes; none for any other kind of type."""
        from ifcopenshell import ifcopenshell_wrapper as schema

        if isinstance(kind, schema.named_type) and isinstance(kind.declared_type(), schema.enumeration_type):
            return list(kind.declared_type().enumeration_items())
        return []

    @classmethod
    def _is_primitive(cls, kind: Any) -> bool:
        """Whether an attribute holds a text, a number, a boolean or an enumeration, and not another entity or a list."""
        from ifcopenshell import ifcopenshell_wrapper as schema

        if isinstance(kind, schema.simple_type):
            return True
        if isinstance(kind, schema.named_type):
            declared: Any = kind.declared_type()
            if isinstance(declared, schema.enumeration_type):
                return True
            if isinstance(declared, schema.type_declaration):
                return cls._is_primitive(declared.declared_type())
        return False
