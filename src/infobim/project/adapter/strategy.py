import importlib
import inspect
import pkgutil
from typing import List, Type

from infobim.project.plugin.capability.strategy import StrategyCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class StrategyCapabilityLoader:
    def get_all(self) -> List[Type[StrategyCapability]]:
        capabilities: List[Type[StrategyCapability]] = []
        package = importlib.import_module("infobim.project.plugin.capability")
        if not hasattr(package, "__path__"):
            return capabilities

        for _, module_name, _ in self._walk_packages_recursive(
            package.__path__,
            package.__name__ + ".",
        ):
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue

            for _, obj in inspect.getmembers(module):
                if not inspect.isclass(obj):
                    continue
                if not issubclass(obj, StrategyCapability):
                    continue
                if obj is StrategyCapability:
                    continue

                metadata = getattr(obj, "METADATA", None)
                if not isinstance(metadata, CapabilityMetadata):
                    continue
                if not metadata.id:
                    continue

                capabilities.append(obj)

        return capabilities

    def _walk_packages_recursive(self, path: List[str], prefix: str):
        for importer, name, is_pkg in pkgutil.iter_modules(path, prefix):
            yield importer, name, is_pkg
            if is_pkg:
                try:
                    package = importlib.import_module(name)
                except Exception:
                    continue

                if hasattr(package, "__path__"):
                    yield from self._walk_packages_recursive(package.__path__, name + ".")
