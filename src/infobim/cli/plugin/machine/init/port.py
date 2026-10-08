from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.handler import StateTransitionHandlerPort


class InfoBIMInitProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the InfoBIM init process.
    """


class InfoBIMInitStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(self, context: CliContextPort) -> InfoBIMInitProcessStatePort:
        """
        Read the project on disk and return the state it is already in.
        """
        ...


class InfoBIMInitStateTransitionHandlerPort(StateTransitionHandlerPort):
    @property
    @abstractmethod
    def current_state(self) -> InfoBIMInitProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> InfoBIMInitProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: InfoBIMInitProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: InfoBIMInitProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: InfoBIMInitProcessStatePort,
        to_state: InfoBIMInitProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def bind_active_state(self, state: InfoBIMInitProcessStatePort) -> None:
        ...
