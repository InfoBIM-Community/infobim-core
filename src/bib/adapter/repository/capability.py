import importlib
import pkgutil
from typing import List, Type
from stack.src.bib.core.port.capability.repository import CapabilityRepository
from stack.src.bib.core.capability.base import Capability

class LocalCapabilityRepository(CapabilityRepository):
    def __init__(self, package_name: str):
        self.package_name = package_name

    def get_capabilities(self) -> List[Type[Capability]]:
        capabilities: List[Type[Capability]] = []
        try:
            package = importlib.import_module(self.package_name)
        except ImportError:
            return []
        if not hasattr(package, "__path__"):
            return []
        for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                module = importlib.import_module(name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, Capability) and attr is not Capability and hasattr(attr, "METADATA"):
                        capabilities.append(attr)
            except Exception:
                pass
        return capabilities
