import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Any, ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort


class TwoDCommandLoader:
    """Discover commands implemented inside the private ``infobim._2d`` package."""

    COMPONENT: ClassVar[str] = "2d"
    COMMAND_PACKAGE: ClassVar[str] = "infobim._2d.plugin.command"

    def __init__(self, logger: LogRepositoryPort) -> None:
        self._logger: LogRepositoryPort = logger

    def get_all(self) -> List[Type[CliCommandPort]]:
        command_package: ModuleType = importlib.import_module(self.COMMAND_PACKAGE)
        package_path: Any = getattr(command_package, "__path__")
        package_prefix: str = f"{command_package.__name__}."
        command_classes: List[Type[CliCommandPort]] = []

        module_info: pkgutil.ModuleInfo
        for module_info in pkgutil.walk_packages(package_path, package_prefix):
            try:
                module: ModuleType = importlib.import_module(module_info.name)
            except ImportError as error:
                self._logger.log_warning(
                    f"Unable to load internal 2D command module "
                    f"'{module_info.name}': {error}"
                )
                continue

            member: Any
            for _, member in inspect.getmembers(module, inspect.isclass):
                if not issubclass(member, CliCommandPort):
                    continue
                if member is CliCommandPort:
                    continue

                metadata: Any = getattr(member, "METADATA", None)
                if getattr(metadata, "logical_component", None) != self.COMPONENT:
                    continue
                if member not in command_classes:
                    command_classes.append(member)

        return command_classes
