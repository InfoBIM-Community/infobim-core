from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort


class DrawingViewDiscoveryProcessStatePort(str, Enum):
    """
    Base enum contract for the Drawing View discovery states.
    """


class DrawingViewDiscoveryStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> DrawingViewDiscoveryProcessStatePort:
        """
        Return the state the discovery of this sheet's views is already in.
        """
        ...


class DrawingViewDiscoveryStateTransitionHandlerPort(ABC):
    @abstractmethod
    def can_transit_to(
        self,
        to_state: DrawingViewDiscoveryProcessStatePort,
    ) -> bool:
        """
        Return whether the machine may move into the given state now.
        """
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: DrawingViewDiscoveryProcessStatePort,
    ) -> None:
        """
        Run the capabilities that bring the given state about.
        """
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: DrawingViewDiscoveryProcessStatePort,
        to_state: DrawingViewDiscoveryProcessStatePort,
    ) -> bool:
        """
        Return whether the state the transition promised was reached.
        """
        ...
