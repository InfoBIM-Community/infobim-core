from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort


class DwgToDxfProcessStatePort(str, Enum):
    """
    Base enum contract for the DWG to DXF conversion states.
    """


class DwgToDxfStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> DwgToDxfProcessStatePort:
        """
        Return the state converting this DWG file is already in.
        """
        ...


class DwgToDxfStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> DwgToDxfProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: DwgToDxfProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: DwgToDxfProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: DwgToDxfProcessStatePort,
        to_state: DwgToDxfProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Execute the DWG to DXF machine and return the conversion result.
        """
        ...
