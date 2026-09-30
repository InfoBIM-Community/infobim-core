from types import ModuleType
from typing import Any, ClassVar, List, Optional, Type
import inspect
import pkgutil
import importlib

from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.domain.port.chain import ChainResponsibilityPort
from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class PrivatePackageCapabilityLoader:
    """
    Discover capabilities implemented inside a private ``infobim`` package.

    The generic ``ChainResponsibilityLoader``/``CapabilityLoader`` skip any
    plugin folder whose name starts with ``_``. Optional stacks such as
    ``_2d`` and ``_3d`` are deliberately hidden that way, so a capability
    living there is never found by the generic scan. A subclass names the
    private capability package in ``CAPABILITY_PACKAGE`` and this loader
    imports it directly.
    """

    CAPABILITY_PACKAGE: ClassVar[str]

    def __init__(self, logger: LogRepositoryPort) -> None:
        self._logger: LogRepositoryPort = logger

    def get(self, capability_id: str) -> Optional[Type[CapabilityPort]]:
        """
        Retrieve the private-package capability declaring ``capability_id``.
        """
        capability_type: Type[CapabilityPort]
        for capability_type in self._capabilities():
            if capability_type.METADATA.id == capability_id:
                return capability_type

        return None

    def get_all(
        self,
        support: Type[ChainResponsibilityPort],
    ) -> List[Type[CapabilityPort]]:
        """
        Retrieve every private-package capability implementing ``support``.
        """
        return [
            capability_type
            for capability_type in self._capabilities()
            if issubclass(capability_type, support)
        ]

    def _capabilities(self) -> List[Type[CapabilityPort]]:
        """
        Retrieve every private-package capability declaring metadata.
        """
        capability_package: ModuleType = importlib.import_module(
            self.CAPABILITY_PACKAGE
        )
        package_path: Any = getattr(capability_package, "__path__")
        package_prefix: str = f"{capability_package.__name__}."
        capability_classes: List[Type[CapabilityPort]] = []

        module_info: pkgutil.ModuleInfo
        for module_info in pkgutil.walk_packages(package_path, package_prefix):
            try:
                module: ModuleType = importlib.import_module(module_info.name)
            except ImportError as error:
                self._logger.log_warning(
                    f"Unable to load private capability module "
                    f"'{module_info.name}': {error}"
                )
                continue

            member: Any
            for _, member in inspect.getmembers(module, inspect.isclass):
                if not issubclass(member, Capability):
                    continue

                metadata: Any = getattr(member, "METADATA", None)
                if not isinstance(metadata, CapabilityMetadata) or not metadata.id:
                    continue
                if member not in capability_classes:
                    capability_classes.append(member)

        return capability_classes
