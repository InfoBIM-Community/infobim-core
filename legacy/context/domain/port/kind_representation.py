from abc import ABC, abstractmethod
from typing import Any, Dict, List


class KindRepresentationResolverPort(ABC):
    @abstractmethod
    def resolve(self, kind: str) -> str:
        """Return the representation URI declared for a kind URI."""
        ...

    @abstractmethod
    def describe(self, representation: str) -> List[Dict[str, Any]]:
        """Return the JSON-LD copy of the representation as declared in the ontology."""
        ...
