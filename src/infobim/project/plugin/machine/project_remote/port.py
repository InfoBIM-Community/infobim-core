from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort


class ProjectRemoteProcessStatePort(str, Enum):
    """
    Base enum contract for InfoBIM remote project connection states.
    """


class ProjectRemoteStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> ProjectRemoteProcessStatePort:
        """
        Read the remote connection on disk and return the state it is
        already in.
        """
        ...
