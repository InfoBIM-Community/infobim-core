from typing import Any, ClassVar, Dict, Optional, Tuple


class IfcDatatype:
    """
    The datatype an IFC value is edited as, an XML Schema one (the datatypes the facades of the ontologies use), and how
    the text a person typed becomes a value of it. A defined type (IfcLengthMeasure, IfcLabel) is the simple type it is
    declared as in the schema: a real, an integer, a boolean, a string.
    """

    XSD: ClassVar[str] = "http://www.w3.org/2001/XMLSchema#"
    BOOLEAN: ClassVar[str] = XSD + "boolean"
    INTEGER: ClassVar[str] = XSD + "integer"
    DOUBLE: ClassVar[str] = XSD + "double"
    STRING: ClassVar[str] = XSD + "string"
    SIMPLE: ClassVar[Dict[str, str]] = {
        "real": DOUBLE,
        "number": DOUBLE,
        "integer": INTEGER,
        "boolean": BOOLEAN,
        "logical": BOOLEAN,
        "string": STRING,
        "binary": STRING,
    }
    #: The quantities, by the template type of their quantity set: a count is whole, the others are measured.
    QUANTITY: ClassVar[Dict[str, str]] = {
        "Q_COUNT": INTEGER,
        "Q_LENGTH": DOUBLE,
        "Q_AREA": DOUBLE,
        "Q_VOLUME": DOUBLE,
        "Q_WEIGHT": DOUBLE,
        "Q_TIME": DOUBLE,
    }

    @classmethod
    def of_type(cls, schema: str, name: str) -> str:
        """The datatype of an IFC type by its name, such as IfcLengthMeasure or IfcLabel."""
        import ifcopenshell

        declaration: Any = ifcopenshell.schema_by_name(schema).declaration_by_name(name)
        declared: Any = declaration.as_type_declaration()
        if declared is None:
            raise LookupError(f"{name} is not a type of the schema {schema}.")
        return cls.of_kind(declared.declared_type())

    @classmethod
    def of_kind(cls, kind: Any) -> str:
        """The datatype of how a type or an attribute is declared; an enumeration or anything else not simple is text."""
        from ifcopenshell import ifcopenshell_wrapper as wrapper

        if isinstance(kind, wrapper.simple_type):
            return cls.SIMPLE[kind.declared_type()]
        if isinstance(kind, wrapper.named_type):
            declared: Any = kind.declared_type()
            if isinstance(declared, wrapper.type_declaration):
                return cls.of_kind(declared.declared_type())
        return cls.STRING

    @classmethod
    def of_quantity(cls, template_type: str) -> Optional[str]:
        """The datatype of a quantity by the template type of its quantity set, or None when it is not a quantity."""
        return cls.QUANTITY.get(template_type)

    @classmethod
    def of_value(cls, value: Any) -> str:
        """The datatype of a value a model holds."""
        if isinstance(value, bool):
            return cls.BOOLEAN
        if isinstance(value, int):
            return cls.INTEGER
        if isinstance(value, float):
            return cls.DOUBLE
        if isinstance(value, str):
            return cls.STRING
        raise ValueError(f"A value of the type {type(value).__name__} cannot be edited.")

    @classmethod
    def convert(cls, text: str, datatype: str) -> Any:
        """
        The value the text is, as the datatype: no value (None) for an empty text. Raises ValueError, saying why, when the
        text is not a value of the datatype.
        """
        stripped: str = text.strip()
        if stripped == "":
            return None
        if datatype == cls.BOOLEAN:
            lowered: str = stripped.lower()
            if lowered not in ("true", "false"):
                raise ValueError(f"{text!r} is not a boolean: use true or false.")
            return lowered == "true"
        if datatype == cls.INTEGER:
            try:
                return int(stripped)
            except ValueError as error:
                raise ValueError(f"{text!r} is not a whole number.") from error
        if datatype == cls.DOUBLE:
            try:
                return float(stripped.replace(",", "."))
            except ValueError as error:
                raise ValueError(f"{text!r} is not a number.") from error
        return text
