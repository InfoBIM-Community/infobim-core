from abc import ABC, abstractmethod


class KindResolverPort(ABC):
    @abstractmethod
    def resolve(self, value: str) -> str:
        """Resolve a kind name to an unambiguous ontology concept URI."""
        ...
