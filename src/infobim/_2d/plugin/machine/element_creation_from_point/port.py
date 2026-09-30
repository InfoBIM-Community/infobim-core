from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort


class ElementCreationFromPointProcessStatePort(str, Enum):
    """
    Base enum contract for the element creation from point states.
    """


class ElementCreationFromPointStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> ElementCreationFromPointProcessStatePort:
        """
        Return the element creation from point state already reached.
        """
        ...


class ElementCreationFromPointStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> ElementCreationFromPointProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> ElementCreationFromPointProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(
        self,
        to_state: ElementCreationFromPointProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: ElementCreationFromPointProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: ElementCreationFromPointProcessStatePort,
        to_state: ElementCreationFromPointProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Execute the element creation from point machine and return the
        result of its last capability.
        """
        ...
