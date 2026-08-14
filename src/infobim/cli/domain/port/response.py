
from abc import ABC, abstractmethod
from ontobdc.cli.domain.response.command import CommandResponse


class ResponseAnsiInformationAdapterPort(ABC):
    @abstractmethod
    def accepts(self, response: CommandResponse) -> bool:
        """
        Check whether this adapter supports the given response.
        """
        ...

    @abstractmethod
    def render(self, response: CommandResponse) -> str:
        """
        Render the response as ANSI text for the InfoBIM CLI.
        """
        ...
