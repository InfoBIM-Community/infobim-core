from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Type

from ontobdc.shared.domain.port.capability import CapabilityPort


class IfcProjectSchemaResolverPort(ABC):
    """
    Reads the IFC schema a project declares.
    """

    @abstractmethod
    def resolve(self, project_path: Path) -> str:
        """
        Return the official buildingSMART release URI of the project's schema.

        :raises IfcProjectSchemaNotResolvedError: when the project declares
            no schema this pipeline can dispatch on.
        """
        ...


class IfcElementClassResolverPort(ABC):
    """
    Answers which IFC class an element of the project is.

    The Loader Capability is addressed by ``(schema_uri, ifc_class)``, and
    the caller only knows the element's GlobalId, so the class has to be
    read from the project before any capability can be resolved. This is
    class identification only: what a Loader Capability then extracts from
    which source is the Loader Capability's own business.
    """

    @abstractmethod
    def resolve(self, project_path: Path, schema_uri: str, element_id: str) -> str:
        """
        Return the IFC class name of the element carrying the given GlobalId.

        :raises IfcElementNotFoundError: when no element of the project
            carries that GlobalId.
        """
        ...


class IfcSchemaLoaderPort(ABC):
    """
    Resolves the Loader Capability of one IFC schema family.

    A schema loader declares the schemas it supports and knows where the
    Loader Capabilities of those schemas live. It is selected by how
    specialized its declaration is, never by a priority field.
    """

    @property
    @abstractmethod
    def supported_schemas(self) -> List[str]:
        """
        Return the release URIs this loader supports, exactly as declared.
        """
        ...

    @abstractmethod
    def loader_capability(self, schema_uri: str, ifc_class: str) -> Type[CapabilityPort]:
        """
        Return the Loader Capability declared for the given pair.

        :raises IfcLoaderCapabilityNotFoundError: when no capability
            declares the pair.
        :raises DuplicateIfcLoaderCapabilityError: when more than one does.
        """
        ...


class IfcSchemaLoaderResolverPort(ABC):
    """
    Selects the schema loader that answers for a resolved release URI.
    """

    @abstractmethod
    def resolve(self, schema_uri: str) -> IfcSchemaLoaderPort:
        """
        Return the most specialized schema loader supporting the schema.

        :raises IfcSchemaLoaderNotFoundError: when no loader supports it.
        """
        ...
