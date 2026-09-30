from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort


class IfcModelCreateProcessStatePort(str, Enum):
    """
    Base enum contract for the IFC model creation states.
    """


class IfcModelCreateStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> IfcModelCreateProcessStatePort:
        """
        Return the state the project's IFC model is already in.
        """
        ...


class IfcModelCreateStateTransitionHandlerPort(ABC):
    @abstractmethod
    def can_transit_to(
        self,
        to_state: IfcModelCreateProcessStatePort,
    ) -> bool:
        """
        Return whether the machine may move into the given state now.
        """
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: IfcModelCreateProcessStatePort,
    ) -> None:
        """
        Run the capability that brings the given state about.
        """
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: IfcModelCreateProcessStatePort,
        to_state: IfcModelCreateProcessStatePort,
    ) -> bool:
        """
        Return whether the state the transition promised was reached.
        """
        ...
