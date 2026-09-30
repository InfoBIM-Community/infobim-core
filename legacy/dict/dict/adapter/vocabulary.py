from typing import ClassVar, Optional, Tuple

from infobim.project.domain.model.contract import ProjectContract


class DictionaryVocabulary:
    """
    The ifcOWL vocabularies a dictionary entry may state an IFC class in.

    A dictionary declares what an element is by making its class a
    subclass of an IFC class, and it names that IFC class in the ifcOWL
    vocabulary of some schema. Several schemas are in use at once: the
    reference dictionary is written against IFC 4 while a project's own
    model may be written against IFC 4.3, and both are legitimate
    statements of the same thing.

    Which vocabularies are recognised is a declared list, never a rule
    over how a URI is spelled. A term of an unregistered vocabulary is not
    an IFC class this tooling knows about — it is read as one more class
    the definition belongs to, which is what it is — instead of being
    turned into an IFC class name by stripping whatever namespace it
    happens to carry.
    """

    IFCOWL_NAMESPACES: ClassVar[Tuple[str, ...]] = (
        ProjectContract.IFCOWL_NAMESPACE,
        "https://standards.buildingsmart.org/IFC/DEV/IFC4/FINAL/OWL#",
        "https://standards.buildingsmart.org/IFC/DEV/IFC4/OWL#",
    )

    PREDEFINED_TYPE_PREFIX: ClassVar[str] = "predefinedType_"

    # The vocabularies a dictionary says the rest of an entry in. An
    # element has a geometry (OMG), the geometry is stated to be good for
    # a level of detail (Digital Construction) and its shape is a
    # primitive of X3D. Each is registered because this reader claims to
    # understand it; a term of anything else is read as one more class
    # the definition belongs to rather than half-understood.
    OMG_NAMESPACE: ClassVar[str] = "https://w3id.org/omg#"
    LIFECYCLE_NAMESPACE: ClassVar[str] = (
        "https://w3id.org/digitalconstruction/0.5/Lifecycle#"
    )
    X3D_NAMESPACE: ClassVar[str] = (
        "https://www.web3d.org/specifications/X3dOntology4.0#"
    )

    HAS_GEOMETRY_PROPERTY: ClassVar[str] = f"{OMG_NAMESPACE}hasGeometry"
    HAS_DESCRIPTION_PROPERTY: ClassVar[str] = (
        f"{OMG_NAMESPACE}hasComplexGeometryDescription"
    )
    HAS_LEVEL_OF_DETAIL_PROPERTY: ClassVar[str] = (
        f"{LIFECYCLE_NAMESPACE}hasLODLevel"
    )
    REPRESENTS_PROPERTY: ClassVar[str] = (
        "http://www.cidoc-crm.org/cidoc-crm/P138_represents"
    )

    @classmethod
    def x3d_local_name_of(cls, uri: str) -> Optional[str]:
        """
        Return the X3D term a URI names, or ``None`` for anything else.
        """
        if not isinstance(uri, str):
            return None

        term: str = uri.strip()
        if not term.startswith(cls.X3D_NAMESPACE) or len(term) <= len(
            cls.X3D_NAMESPACE
        ):
            return None

        return term[len(cls.X3D_NAMESPACE):]

    @classmethod
    def ifc_local_name_of(cls, uri: str) -> Optional[str]:
        """
        Return the IFC term a registered ifcOWL URI names, or ``None``.
        """
        if not isinstance(uri, str):
            return None

        term: str = uri.strip()
        namespace: str
        for namespace in cls.IFCOWL_NAMESPACES:
            if term.startswith(namespace) and len(term) > len(namespace):
                return term[len(namespace):]

        return None

    @classmethod
    def predefined_type_property(cls, uri: str) -> Optional[str]:
        """
        Return the IFC class a ``predefinedType_`` property belongs to.

        A restriction on ``predefinedType_IfcSanitaryTerminal`` says which
        predefined type of that class the definition is, so the property
        names the class as much as the type does.
        """
        local_name: Optional[str] = cls.ifc_local_name_of(uri)
        if local_name is None or not local_name.startswith(
            cls.PREDEFINED_TYPE_PREFIX
        ):
            return None

        owner: str = local_name[len(cls.PREDEFINED_TYPE_PREFIX):]

        return owner if owner else None

    @staticmethod
    def local_name_of(uri: str) -> str:
        """
        Return the last term of any URI, for what a definition is called.
        """
        term: str = uri.strip()
        for separator in ("#", "/"):
            if separator in term:
                term = term.rsplit(separator, 1)[1] or term

        return term
