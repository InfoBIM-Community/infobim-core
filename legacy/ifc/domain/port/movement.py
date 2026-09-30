from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Tuple


class IfcElementMoverPort(ABC):
    @abstractmethod
    def displace(
        self,
        model_path: Path,
        global_id: str,
        displacement: Dict[str, float],
    ) -> Dict[str, Tuple[float, float, float]]:
        """
        Add a displacement to the element's own placement and persist it.

        Returns the position the element moved from and the position it
        moved to, both in the model's own coordinates.
        """
        ...
