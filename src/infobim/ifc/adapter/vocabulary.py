from typing import ClassVar, Dict, Optional

from infobim.project.domain.model.contract import ProjectContract


class IfcSchemaVocabulary:
    """
    The registered pairs of ifcOWL vocabulary and IFC release URI.

    An IFC entity is typed with the vocabulary of its schema —
    ``https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#IfcProject`` —
    while the pipeline dispatches on the official release URI of that same
    schema — ``https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/``.
    Two identifiers of one schema, and this is where the runtime goes from
    either one to the other.

    The relation is a declared mapping, not a rewriting rule. A vocabulary
    is supported by being registered here, so a URI that merely looks like
    an ifcOWL term of some unregistered schema resolves to ``None`` and the
    caller reports it as unknown. Synthesizing a release URI from whatever
    segment a URI happens to carry would invent a schema nobody supports
    and let it through dispatch as if it were declared.

    Supporting another schema is adding its pair to ``VOCABULARIES``.
    """

    VOCABULARIES: ClassVar[Dict[str, str]] = {
        ProjectContract.IFCOWL_NAMESPACE: ProjectContract.DEFAULT_IFC_SCHEMA,
    }

    IFC_PROJECT_LOCAL_NAME: ClassVar[str] = "IfcProject"
    GLOBAL_ID_LOCAL_NAME: ClassVar[str] = "globalId_IfcRoot"

    @classmethod
    def namespace_prefix_of(cls, class_uri: str) -> Optional[str]:
        """
        Return the registered ifcOWL namespace a term belongs to.
        """
        if not isinstance(class_uri, str):
            return None

        uri: str = class_uri.strip()
        namespace: str
        for namespace in cls.VOCABULARIES:
            if uri.startswith(namespace) and len(uri) > len(namespace):
                return namespace

        return None

    @classmethod
    def release_uri_of(cls, class_uri: str) -> Optional[str]:
        """
        Return the release URI of the schema a registered ifcOWL term belongs to.

        A term of an unregistered vocabulary resolves to ``None``: it is
        unknown, not a schema to be derived from its spelling.
        """
        namespace: Optional[str] = cls.namespace_prefix_of(class_uri)
        if namespace is None:
            return None

        return cls.VOCABULARIES[namespace]

    @classmethod
    def local_name_of(cls, class_uri: str) -> Optional[str]:
        """
        Return the term a registered ifcOWL URI names, such as ``IfcWall``.
        """
        namespace: Optional[str] = cls.namespace_prefix_of(class_uri)
        if namespace is None:
            return None

        return class_uri.strip()[len(namespace):]

    @classmethod
    def namespace_of(cls, schema_uri: str) -> Optional[str]:
        """
        Return the ifcOWL namespace registered for a release URI.

        A release URI with no registered vocabulary resolves to ``None``,
        for the same reason: an unsupported schema is unsupported, not a
        namespace to be spelled out from its own URI.
        """
        if not isinstance(schema_uri, str):
            return None

        uri: str = schema_uri.strip()
        namespace: str
        release_uri: str
        for namespace, release_uri in cls.VOCABULARIES.items():
            if release_uri == uri:
                return namespace

        return None

    @classmethod
    def term_of(cls, namespace: str, local_name: str) -> str:
        """
        Return the URI of a term inside an ifcOWL namespace.
        """
        return f"{namespace}{local_name}"
