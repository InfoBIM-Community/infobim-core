from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class ProjectRefreshProcessStatePort(str, Enum):
    """
    Base enum contract for InfoBIM project refresh states.
    """


class ProjectRefreshStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> ProjectRefreshProcessStatePort:
        """
        Read the project after container refresh and return the InfoBIM
        refresh state it is already in.
        """
        ...


class ProjectRefreshStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> ProjectRefreshProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: ProjectRefreshProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: ProjectRefreshProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: ProjectRefreshProcessStatePort,
        to_state: ProjectRefreshProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the InfoBIM project refresh stage after the OntoBDC
        container refresh stage finishes.
        """
        ...
