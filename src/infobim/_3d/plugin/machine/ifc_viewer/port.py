from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort


class IfcViewerProcessStatePort(str, Enum):
    """
    Base enum contract for the IFC 3D viewer states.
    """


class IfcViewerStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> IfcViewerProcessStatePort:
        """
        Return the state viewing this IFC file is already in.
        """
        ...


class IfcViewerStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> IfcViewerProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: IfcViewerProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: IfcViewerProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: IfcViewerProcessStatePort,
        to_state: IfcViewerProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Execute the IFC 3D viewer machine and return the viewer result.
        """
        ...
