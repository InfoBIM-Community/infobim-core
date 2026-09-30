from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort


class DictionaryEntityCreateProcessStatePort(str, Enum):
    """
    Base enum contract for the dictionary entity creation states.
    """


class DictionaryEntityCreateStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> DictionaryEntityCreateProcessStatePort:
        """
        Return the state this dictionary entity creation is already in.

        The target model's health is a fact of the model and is read by the
        same standalone checks every other IFC flow reads it with. What
        this run downloaded and what it understood of it are facts of the
        run, read from the execution itself, so a process that starts
        again downloads and reads again instead of trusting what an
        earlier one wrote down.
        """
        ...


class DictionaryEntityCreateStateTransitionHandlerPort(ABC):
    @abstractmethod
    def can_transit_to(
        self,
        to_state: DictionaryEntityCreateProcessStatePort,
    ) -> bool:
        """
        Return whether the machine may move into the given state now.
        """
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: DictionaryEntityCreateProcessStatePort,
    ) -> None:
        """
        Run the capability that brings the given state about.
        """
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: DictionaryEntityCreateProcessStatePort,
        to_state: DictionaryEntityCreateProcessStatePort,
    ) -> bool:
        """
        Return whether the state the transition promised was reached.
        """
        ...
