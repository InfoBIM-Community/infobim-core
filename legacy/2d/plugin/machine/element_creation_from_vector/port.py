from abc import ABC, abstractmethod
from typing import Any
from importlib import import_module

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.context.adapter.taxonomy import MACHINE_PACKAGE

DxfVectorProcessState: Any = import_module(MACHINE_PACKAGE + ".state").DxfVectorProcessState


class DxfVectorStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(self, context: CliContextPort) -> DxfVectorProcessState:
        ...


class DxfVectorStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> DxfVectorProcessState:
        ...

    @abstractmethod
    def bind_active_state(self, state: DxfVectorProcessState) -> None:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: DxfVectorProcessState) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: DxfVectorProcessState) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self, from_state: DxfVectorProcessState, to_state: DxfVectorProcessState
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        ...
