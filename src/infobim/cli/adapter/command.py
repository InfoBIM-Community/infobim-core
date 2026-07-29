
from typing import List, Type
from infobim.shared.adapter.loader import CommandLoader
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.domain.port.loader import CommandLoaderPort
from ontobdc.cli.adapter.command import CliCommandRunAdapter as OntoBDCCliCommandRunAdapter


class CliCommandRunAdapter(OntoBDCCliCommandRunAdapter):
    """
    Adapter for running InfoBIM CLI commands.
    """
    @classmethod
    def make(cls, args: List[str], logger: LogRepositoryPort, check_level: int = 1, loader_class: Type[CommandLoaderPort] = None) -> CliCommandPort:
        """
        Create a command adapter from raw CLI arguments.
        """
        if loader_class is None:
            loader_class = CommandLoader

        return super().make(
            args,
            logger,
            check_level,
            loader_class,
            defer_check=True,
        )
