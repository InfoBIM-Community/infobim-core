
from typing import Any
from argparse import ArgumentParser
from abc import ABC, abstractmethod
from stack.src.bib.core.capability import Capability


class CapabilityCliStrategy(ABC):

    @abstractmethod
    def setup_parser(self, parser: ArgumentParser) -> None:
        pass

    @abstractmethod
    def run(self, console: Any, args: Any, capability: Capability) -> None:
        pass

    @abstractmethod
    def render(self, console: Any, args: Any, capability: Capability, result: Any) -> None:
        pass
