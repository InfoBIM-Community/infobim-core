from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort


class ThreeDViewProcessStatePort(str, Enum):
    """
    Base enum contract for InfoBIM 3D viewer launch states.
    """


class ThreeDViewStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> ThreeDViewProcessStatePort:
        """
        Return the state opening the 3D viewer for the target Project is
        already in.
        """
        ...
