from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort


class ProjectCreateProcessStatePort(str, Enum):
    """
    Base enum contract for InfoBIM project creation states.
    """


class ProjectCreateStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> ProjectCreateProcessStatePort:
        """
        Read the project on disk and return the state it is already in.
        """
        ...
