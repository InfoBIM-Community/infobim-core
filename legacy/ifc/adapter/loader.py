import inspect
import importlib
from typing import Any, ClassVar, List, Type

from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.adapter.loader import PluginLoader
from ontobdc.shared.domain.port.capability import CapabilityPort

from infobim.ifc.domain.exception.conversion import (
    DuplicateIfcLoaderCapabilityError,
    DuplicateIfcWriterCapabilityError,
    IfcConversionError,
    IfcLoaderCapabilityNotFoundError,
    IfcWriterCapabilityNotFoundError,
)
from infobim.ifc.domain.model.capability import IfcCapabilityMetadata
from infobim.ifc.domain.port.loader import IfcCapabilityPackageLoaderPort


class IfcCapabilityPackageLoader(PluginLoader, IfcCapabilityPackageLoaderPort):
    """
    Discovers IFC child capabilities inside one designated package.

    The generic capability loader walks every ``<domain>/plugin/capability``
    package of every root package it is given; this walks one package and
    nothing else, so a source loader is resolved only from the IFC loader
    package and a writer only from the IFC writer package. Those capabilities
    stay discoverable through the generic surface as well — restricting
    discovery here is about what ``IfcToIfcxCapability`` may select, not
    about hiding them.

    Every candidate is returned, duplicates included. The generic loader
    keeps the first capability of a repeated ``METADATA.id`` and drops the
    rest silently, which would swallow exactly the invalid configuration
    this family has to report.
    """

    PACKAGE: ClassVar[str] = ""
    DUPLICATE_ERROR: ClassVar[Type[IfcConversionError]] = IfcConversionError
    MISSING_ERROR: ClassVar[Type[IfcConversionError]] = IfcConversionError

    def get_all(self, resource: str = "capability") -> List[Type[CapabilityPort]]:
        """
        Return every IFC capability declared inside the designated package.

        A package that cannot be imported, or a module inside it that cannot
        be loaded, stops the resolution instead of narrowing it: a candidate
        skipped quietly here is a capability the caller would be told does
        not exist, or a duplicate registration that would go unreported.
        """
        package: Any = importlib.import_module(self.PACKAGE)
        if not hasattr(package, "__path__"):
            raise self.MISSING_ERROR(
                f"{self.PACKAGE} is not a package and declares no capability."
            )

        capabilities: List[Type[CapabilityPort]] = []
        package_prefix: str = package.__name__ + "."
        for _, name, _ in self._walk_packages_recursive(
            package.__path__,
            package_prefix,
            current_depth=1,
            max_depth=10,
        ):
            module: Any = importlib.import_module(name)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if not issubclass(obj, Capability) or inspect.isabstract(obj):
                    continue

                metadata: Any = getattr(obj, "METADATA", None)
                if not isinstance(metadata, IfcCapabilityMetadata):
                    continue

                if obj in capabilities:
                    continue

                capabilities.append(obj)

        return capabilities

    def resolve(self, schema_uri: str, ifc_class: str) -> Type[CapabilityPort]:
        """
        Return the single capability declaring the given pair.
        """
        matches: List[Type[CapabilityPort]] = [
            capability
            for capability in self.get_all()
            if capability.METADATA.schema_uri == schema_uri
            and capability.METADATA.ifc_class == ifc_class
        ]

        if len(matches) > 1:
            raise self.DUPLICATE_ERROR(
                f"{len(matches)} capabilities in {self.PACKAGE} declare "
                f"({schema_uri}, {ifc_class}): "
                f"{sorted(capability.METADATA.id for capability in matches)}."
            )

        if not matches:
            raise self.MISSING_ERROR(
                f"No capability in {self.PACKAGE} declares "
                f"({schema_uri}, {ifc_class})."
            )

        return matches[0]


class IfcLoaderCapabilityLoader(IfcCapabilityPackageLoader):
    """
    Resolves the Loader Capability of an ``(schema_uri, ifc_class)`` pair.
    """

    PACKAGE: ClassVar[str] = "infobim.ifc.plugin.capability.loader"
    DUPLICATE_ERROR: ClassVar[Type[IfcConversionError]] = (
        DuplicateIfcLoaderCapabilityError
    )
    MISSING_ERROR: ClassVar[Type[IfcConversionError]] = (
        IfcLoaderCapabilityNotFoundError
    )


class IfcWriterCapabilityLoader(IfcCapabilityPackageLoader):
    """
    Resolves the Writer Capability of an ``(schema_uri, ifc_class)`` pair.

    The writer side has one target schema at a time, so this is plain
    infrastructure: there is no second family of pluggable writer loaders
    competing through their own ``supported_schemas`` declaration.
    """

    PACKAGE: ClassVar[str] = "infobim.ifc.plugin.capability.writer"
    DUPLICATE_ERROR: ClassVar[Type[IfcConversionError]] = (
        DuplicateIfcWriterCapabilityError
    )
    MISSING_ERROR: ClassVar[Type[IfcConversionError]] = (
        IfcWriterCapabilityNotFoundError
    )
