from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class A3LlmSuggestionProcessStatePort(str, Enum):
    pass


class A3LlmSuggestionStateEvaluatorPort(ABC):
    @property
    @abstractmethod
    def process_state_class(self) -> Type[A3LlmSuggestionProcessStatePort]:
        ...

    @abstractmethod
    def evaluate(self, context: CliContextPort) -> A3LlmSuggestionProcessStatePort:
        ...


class A3LlmSuggestionStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def context(self) -> CliContextPort:
        ...

    @property
    @abstractmethod
    def target_path(self) -> Path:
        ...

    @property
    @abstractmethod
    def current_state(self) -> A3LlmSuggestionProcessStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[A3LlmSuggestionProcessStatePort]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: A3LlmSuggestionProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: A3LlmSuggestionProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: A3LlmSuggestionProcessStatePort,
        to_state: A3LlmSuggestionProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        ...
