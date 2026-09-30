from typing import ClassVar, Dict, Optional

from infobim.project.domain.model.contract import ProjectContract


class IfcSchemaIdentifier:
    """
    The registered pairs of IFC release URI and IFC reader schema identifier.

    A project declares its schema as the official buildingSMART release
    URI — ``https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/`` — and
    the STEP reader names schemas its own way, with identifiers such as
    ``IFC4X3_ADD2``. Neither spelling turns into the other by rewriting
    characters, so the relation is declared here, the way
    ``IfcSchemaVocabulary`` declares the ifcOWL side of it. A release URI
    that is not registered is unsupported, not a schema to be guessed from
    the shape of its own URI.

    ``IFC4X3_ADD2`` is the addendum of the IFC 4.3 family this project
    writes: it is what the reader produces for that family, so a model
    created here and a model the reader created elsewhere carry the same
    identifier. Comparison between a model and its project is by family
    (``IFC4X3``), because an addendum is a revision of one schema rather
    than another schema, and a file authored against ``IFC4X3_ADD1`` is
    still the IFC 4.3 the project declares.
    """

    REGISTERED: ClassVar[Dict[str, str]] = {
        ProjectContract.DEFAULT_IFC_SCHEMA: "IFC4X3_ADD2",
    }

    FAMILY_SEPARATOR: ClassVar[str] = "_"

    @classmethod
    def identifier_of(cls, schema_uri: str) -> Optional[str]:
        """
        Return the reader's schema identifier registered for a release URI.
        """
        if not isinstance(schema_uri, str):
            return None

        return cls.REGISTERED.get(schema_uri.strip())

    @classmethod
    def schema_uri_of(cls, identifier: str) -> Optional[str]:
        """
        Return the release URI registered for a reader schema identifier.
        """
        if not isinstance(identifier, str):
            return None

        wanted: str = identifier.strip()
        schema_uri: str
        registered: str
        for schema_uri, registered in cls.REGISTERED.items():
            if registered == wanted:
                return schema_uri

        return None

    @classmethod
    def family_of(cls, identifier: str) -> Optional[str]:
        """
        Return the schema family an identifier belongs to.

        ``IFC4X3_ADD2`` and ``IFC4X3_TC1`` are both ``IFC4X3``: one schema,
        successive addenda.
        """
        if not isinstance(identifier, str) or not identifier.strip():
            return None

        return identifier.strip().split(cls.FAMILY_SEPARATOR, 1)[0]
