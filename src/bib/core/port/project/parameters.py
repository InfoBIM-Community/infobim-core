
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict


class ProjectParametersPort(ABC):
    @abstractmethod
    def get_value(self, key_path: str, delivery_id: Optional[str] = None) -> Any:
        pass

    @abstractmethod
    def get_merged(self, delivery_id: Optional[str] = None) -> Dict[str, Any]:
        pass
