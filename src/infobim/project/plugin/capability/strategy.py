from abc import abstractmethod
from typing import Any

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability


class StrategyCapability(TransformationCapability):
    @abstractmethod
    def matches(
        self,
        document_kind: str,
        element_name: str,
        context: CliContextPort,
    ) -> bool:
        ...

    def priority(
        self,
        document_kind: str,
        element_name: str,
        context: CliContextPort,
    ) -> int:
        return 0
