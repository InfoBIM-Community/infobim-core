from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.response.command import CommandResponse


class IfcElementListProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the listing of the IFC elements of a project.
    """


class IfcElementListStateTransitionHandlerPort(ABC):
    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        List the IFC elements of the models the project holds.
        """
        ...
