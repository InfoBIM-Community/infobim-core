import inspect
import pkgutil
import importlib
from typing import Any, ClassVar, List, Optional, Tuple, Type

from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.ifc.adapter.loader import IfcLoaderCapabilityLoader
from infobim.ifc.domain.exception.conversion import IfcSchemaLoaderNotFoundError
from infobim.ifc.domain.port.loader import IfcCapabilityPackageLoaderPort
from infobim.ifc.domain.port.schema import (
    IfcSchemaLoaderPort,
    IfcSchemaLoaderResolverPort,
)
from infobim.project.domain.model.contract import ProjectContract


class IfcSchemaLoader(IfcSchemaLoaderPort):
    """
    Base of the loaders that answer for a family of IFC schemas.

    A schema loader declares the release URIs it supports and resolves the
    Loader Capability of a class inside the IFC loader package. Supporting a
    new schema means shipping a loader that declares it; it never means
    editing a table of schemas somewhere central.
    """

    SUPPORTED_SCHEMAS: ClassVar[Tuple[str, ...]] = ()

    def __init__(
        self,
        capability_loader: Optional[IfcCapabilityPackageLoaderPort] = None,
    ) -> None:
        self._capability_loader: IfcCapabilityPackageLoaderPort = (
            capability_loader or IfcLoaderCapabilityLoader()
        )

    @property
    def supported_schemas(self) -> List[str]:
        return list(self.SUPPORTED_SCHEMAS)

    def loader_capability(
        self,
        schema_uri: str,
        ifc_class: str,
    ) -> Type[CapabilityPort]:
        return self._capability_loader.resolve(schema_uri, ifc_class)


class Ifc4X3SchemaLoader(IfcSchemaLoader):
    """
    Schema loader for the current default release, ``IFC4_3``.
    """

    SUPPORTED_SCHEMAS: ClassVar[Tuple[str, ...]] = (
        ProjectContract.DEFAULT_IFC_SCHEMA,
    )


class IfcSchemaLoaderResolver(IfcSchemaLoaderResolverPort):
    """
    Selects the schema loader that answers for a resolved release URI.

    Selection is specialization, not preference: every loader declaring the
    exact release URI is a candidate, and the one that declares the fewest
    schemas wins, because a loader written for one schema knows it better
    than a loader written for five. A tie is broken by the candidate already
    at index ``0`` of the collected array — no secondary sort, no priority
    field, no fallback to a neighbouring schema.
    """

    PACKAGE: ClassVar[str] = "infobim.ifc.adapter"

    def get_all(self) -> List[IfcSchemaLoaderPort]:
        """
        Return one instance of every schema loader shipped in the package.
        """
        loaders: List[IfcSchemaLoaderPort] = []
        package: Any = importlib.import_module(self.PACKAGE)
        if not hasattr(package, "__path__"):
            raise IfcSchemaLoaderNotFoundError(
                f"{self.PACKAGE} is not a package and declares no schema loader."
            )

        prefix: str = package.__name__ + "."
        seen: List[Type[IfcSchemaLoaderPort]] = []
        for _, name, _ in pkgutil.iter_modules(package.__path__, prefix):
            module: Any = importlib.import_module(name)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if not issubclass(obj, IfcSchemaLoader) or obj is IfcSchemaLoader:
                    continue
                if inspect.isabstract(obj) or obj in seen:
                    continue

                seen.append(obj)
                loaders.append(obj())

        return loaders

    def resolve(self, schema_uri: str) -> IfcSchemaLoaderPort:
        candidates: List[IfcSchemaLoaderPort] = [
            loader
            for loader in self.get_all()
            if schema_uri in loader.supported_schemas
        ]

        if not candidates:
            raise IfcSchemaLoaderNotFoundError(
                f"No IFC schema loader supports the schema {schema_uri}."
            )

        specialization: int = min(
            len(loader.supported_schemas) for loader in candidates
        )

        return [
            loader
            for loader in candidates
            if len(loader.supported_schemas) == specialization
        ][0]
