from ontobdc.shared.domain.model.capability import CapabilityMetadata


class IfcCapabilityMetadata(CapabilityMetadata):
    """
    Metadata of a capability selected by the IFC schema and the IFC class.

    An IFC child capability is never chosen by its module name, its file
    name or its Python class name: it declares which IFC schema it answers
    for and which IFC class it converts, and the IFC loaders resolve it by
    that pair alone.

    ``schema_uri`` carries the official buildingSMART release URI on the
    source side (for instance
    ``https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/``) and the
    writer-side schema identifier on the target side (currently the literal
    ``IFC5-Alpha``). ``ifc_class`` is the class name in the IFC schema —
    ``IfcGrid``, ``IfcWall`` — never the name of the Python class that
    implements the capability.

    The field is ``schema_uri`` rather than ``schema`` because a field named
    ``schema`` shadows ``BaseModel.schema``; every caller reads
    ``metadata.schema_uri``.
    """

    schema_uri: str
    ifc_class: str
