from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort


class GeometricProductCreateProcessStatePort(str, Enum):
    """
    Base enum contract for the geometric product creation states.
    """


class GeometricProductCreateStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> GeometricProductCreateProcessStatePort:
        """
        Return the state the geometric product creation is already in.

        Two of the states this machine passes through are facts of the run
        rather than facts of the model — the position and the geometry a
        command defined — so they are read from the context of the current
        execution and recomputed when it starts again, never written down
        as flags to be read back later.
        """
        ...


class GeometricProductCreateStateTransitionHandlerPort(ABC):
    @abstractmethod
    def can_transit_to(
        self,
        to_state: GeometricProductCreateProcessStatePort,
    ) -> bool:
        """
        Return whether the machine may move into the given state now.
        """
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: GeometricProductCreateProcessStatePort,
    ) -> None:
        """
        Run the capability that brings the given state about.
        """
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: GeometricProductCreateProcessStatePort,
        to_state: GeometricProductCreateProcessStatePort,
    ) -> bool:
        """
        Return whether the state the transition promised was reached.
        """
        ...


class IfcElementMoveProcessStatePort(str, Enum):
    """
    Base enum contract for the IFC element move states.
    """


class IfcElementMoveStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> IfcElementMoveProcessStatePort:
        """
        Return the state this element move is already in.

        The target model's health is a fact of the model and is read by
        the same standalone checks every other IFC flow reads it with.
        Which element this run moves, by how much, and where it ended up
        are facts of the run, read from the execution itself, so a
        process that starts again resolves and displaces again instead of
        trusting what an earlier one wrote down.
        """
        ...


class IfcElementMoveStateTransitionHandlerPort(ABC):
    @abstractmethod
    def can_transit_to(
        self,
        to_state: IfcElementMoveProcessStatePort,
    ) -> bool:
        """
        Return whether the machine may move into the given state now.
        """
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: IfcElementMoveProcessStatePort,
    ) -> None:
        """
        Run the capability that brings the given state about.
        """
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: IfcElementMoveProcessStatePort,
        to_state: IfcElementMoveProcessStatePort,
    ) -> bool:
        """
        Return whether the state the transition promised was reached.
        """
        ...


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
