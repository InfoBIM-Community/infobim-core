class IfcConversionError(Exception):
    """
    Base of every failure the IFC → IFCX pipeline reports by itself.

    The pipeline resolves a schema, a schema loader, a Loader Capability and
    a Writer Capability before anything is converted. Each of those steps
    fails for a reason a caller can act on, so each raises its own error
    instead of a bare ``ValueError`` that says nothing about which step gave
    up.
    """


class IfcProjectSchemaNotResolvedError(IfcConversionError):
    """
    The project declares no IFC schema this pipeline can dispatch on.

    The schema is read from the IfcProject in
    ``.__infobim__/payload/triple/ifc_project.ttl`` and is the official
    buildingSMART release URI its ifcOWL type resolves to. A project whose
    vocabulary resolves to nothing known fails here: the default release URI
    is a fallback for writing a schema that is missing, never a way to
    reinterpret existing project data.
    """


class IfcSchemaLoaderNotFoundError(IfcConversionError):
    """
    No schema loader declares the release URI the project resolved to.

    Schema loaders declare the schemas they support exactly. A release URI
    no loader lists is not substituted by a neighbouring schema.
    """


class IfcElementNotFoundError(IfcConversionError):
    """
    No IFC element in the project carries the requested GlobalId.

    The element is looked up to learn which IFC class it is, which is what
    selects the Loader Capability. A GlobalId absent from both the ifcOWL
    triples and the IFC/STEP resources of the project has no class to
    dispatch on.
    """


class DuplicateIfcLoaderCapabilityError(IfcConversionError):
    """
    Two Loader Capabilities declare the same ``(schema_uri, ifc_class)``.

    That pair is the address of exactly one capability. Two capabilities
    answering for it is an invalid plugin configuration, so it is reported
    rather than resolved by picking one of them.
    """


class IfcLoaderCapabilityNotFoundError(IfcConversionError):
    """
    No Loader Capability answers for the requested ``(schema_uri, ifc_class)``.
    """


class DuplicateIfcWriterCapabilityError(IfcConversionError):
    """
    Two Writer Capabilities declare the same ``(schema_uri, ifc_class)``.
    """


class IfcWriterCapabilityNotFoundError(IfcConversionError):
    """
    No Writer Capability answers for the requested ``(schema_uri, ifc_class)``.
    """
