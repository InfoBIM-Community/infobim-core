from abc import ABC, abstractmethod
from typing import List, Type
from stack.src.bib.core.capability.base import Capability

class CapabilityRepository(ABC):
    @abstractmethod
    def get_capabilities(self) -> List[Type[Capability]]:
        pass
