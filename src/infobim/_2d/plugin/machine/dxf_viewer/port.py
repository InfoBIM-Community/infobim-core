from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort


class DxfViewerProcessStatePort(str, Enum):
    """
    Base enum contract for the DXF viewer states.
    """


class DxfViewerStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> DxfViewerProcessStatePort:
        """
        Return the state viewing this DXF file is already in.
        """
        ...


class DxfViewerStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> DxfViewerProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: DxfViewerProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: DxfViewerProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: DxfViewerProcessStatePort,
        to_state: DxfViewerProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Execute the DXF viewer machine and return the viewer result.
        """
        ...
