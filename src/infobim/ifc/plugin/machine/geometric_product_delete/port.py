from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort


class GeometricProductDeleteProcessStatePort(str, Enum):
    """
    Base enum contract for the geometric product deletion states.
    """


class GeometricProductDeleteStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> GeometricProductDeleteProcessStatePort:
        """
        Return the state the deletion of this geometric product is already in.

        The target model's health is a fact of the model. The element
        identifier is a fact of this run and is read from the execution
        itself, so a process that starts again resolves and validates the
        identifier instead of trusting what an earlier one wrote down.
        """
        ...


class GeometricProductDeleteStateTransitionHandlerPort(ABC):
    @abstractmethod
    def can_transit_to(
        self,
        to_state: GeometricProductDeleteProcessStatePort,
    ) -> bool:
        """
        Return whether the machine may move into the given state now.
        """
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: GeometricProductDeleteProcessStatePort,
    ) -> None:
        """
        Run the capability that brings the given state about.
        """
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: GeometricProductDeleteProcessStatePort,
        to_state: GeometricProductDeleteProcessStatePort,
    ) -> bool:
        """
        Return whether the state the transition promised was reached.
        """
        ...
