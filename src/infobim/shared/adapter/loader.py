import importlib
import inspect
import os
from typing import Any, List, Type
from infobim.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError
from ontobdc.shared.adapter.capability import Capability
from ontobdc.shared.adapter.loader import (
    CapabilityLoader as OntoBDCCapabilityLoader,
    CommandLoader as OntoBDCCommandLoader,
    ParameterLoader as OntoBDCParameterLoader,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.capability import CapabilityPort


class CommandLoader(OntoBDCCommandLoader):
    """
    Command loader for plugin commands.
    """
    def _make_config_data_adapter(self) -> ConfigDataAdapter:
        try:
            return ConfigDataAdapter()
        except ProjectRootDirectoryNotSetError:
            return ConfigDataAdapter(root_dir=os.getcwd())

    def _list_plugin_folder(self, resource: str) -> List[str]:
        discovered: List[str] = []
        infobim_root: str = str(self._make_config_data_adapter().script_dir)
        
        try:
            discovered = self._scan_directory(resource, infobim_root, "infobim", discovered)
            module_dir = os.path.join(infobim_root, "module")
            if os.path.isdir(module_dir):
                discovered = self._scan_directory(resource, module_dir, "infobim.module", discovered)
        except Exception:
            return []

        return discovered


class ParameterLoader(OntoBDCParameterLoader):
    """Discover InfoBIM parameter strategies."""

    def _make_config_data_adapter(self) -> ConfigDataAdapter:
        try:
            return ConfigDataAdapter()
        except ProjectRootDirectoryNotSetError:
            return ConfigDataAdapter(root_dir=os.getcwd())

    def _list_plugin_folder(self, resource: str) -> List[str]:
        discovered: List[str] = []
        infobim_root: str = str(self._make_config_data_adapter().script_dir)

        try:
            discovered = self._scan_directory(
                resource,
                infobim_root,
                "infobim",
                discovered,
            )
            module_dir: str = os.path.join(infobim_root, "module")
            if os.path.isdir(module_dir):
                discovered = self._scan_directory(
                    resource,
                    module_dir,
                    "infobim.module",
                    discovered,
                )
        except Exception:
            return []

        return discovered


class CapabilityLoader(OntoBDCCapabilityLoader):
    """
    Capability loader for InfoBIM plugins.
    """
    def _make_config_data_adapter(self) -> ConfigDataAdapter:
        try:
            return ConfigDataAdapter()
        except ProjectRootDirectoryNotSetError:
            return ConfigDataAdapter(root_dir=os.getcwd())

    def _list_plugin_folder(self, resource: str) -> List[str]:
        discovered: List[str] = []
        infobim_root: str = str(self._make_config_data_adapter().script_dir)

        try:
            discovered = self._scan_directory(resource, infobim_root, "infobim", discovered)
            module_dir: str = os.path.join(infobim_root, "module")
            if os.path.isdir(module_dir):
                discovered = self._scan_directory(resource, module_dir, "infobim.module", discovered)
        except Exception:
            return []

        return discovered

    def get_all(self, resource: str = "capability") -> List[Type[CapabilityPort]]:
        capabilities: List[Type[CapabilityPort]] = []

        for pkg_name in self._list_plugin_folder(resource):
            try:
                package = importlib.import_module(pkg_name)
            except ImportError:
                continue

            if not hasattr(package, "__path__"):
                continue

            resource_pkg_name = f"{pkg_name}.{resource}"
            try:
                resource_package = importlib.import_module(resource_pkg_name)
            except ImportError:
                continue

            if not hasattr(resource_package, "__path__"):
                continue

            package_prefix = getattr(resource_package, "__name__", resource_pkg_name) + "."
            for _, name, _ in self._walk_packages_recursive(
                resource_package.__path__,
                package_prefix,
                current_depth=1,
                max_depth=10,
            ):
                try:
                    module = importlib.import_module(name)
                    for _, obj in inspect.getmembers(module):
                        if not inspect.isclass(obj):
                            continue
                        try:
                            if not issubclass(obj, Capability):
                                continue
                        except TypeError:
                            continue

                        metadata_obj: Any = getattr(obj, "METADATA", None)
                        if not isinstance(metadata_obj, CapabilityMetadata):
                            continue
                        if not metadata_obj.id:
                            continue

                        capabilities.append(obj)
                except Exception:
                    continue

        return capabilities
