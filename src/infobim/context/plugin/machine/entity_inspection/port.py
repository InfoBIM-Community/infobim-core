from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort


class EntityInspectionProcessStatePort(str, Enum):
    """Base enum contract for InfoBIM entity inspection states."""


class EntityInspectionStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(self, context: CliContextPort) -> EntityInspectionProcessStatePort:
        """Return the entity inspection state already reached."""
        ...
