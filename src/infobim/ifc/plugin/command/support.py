from __future__ import annotations

from typing import Any, Dict

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.shared.adapter.capability import Capability, CapabilityExecutor


class IfcProjectQueryCommand(CliCommandPort):
    """Shared CLI boundary for capability-backed IFC Project queries."""

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    @property
    def context(self) -> CliContextPort:
        context: CliContextPort = self._request.context
        if context is None:
            raise CliCommandArgumentException(
                "Missing CLI context. Cannot resolve InfoBIM Project."
            )
        return context

    def require_project(self) -> str:
        project_path: str = str(
            self.context.get_parameter_value("project_path") or ""
        ).strip()
        if not project_path:
            raise CliCommandArgumentException(
                "Could not resolve InfoBIM Project. Pass --project-id <GlobalId> "
                "or --project <selector>, or run this command inside an InfoBIM "
                "Project / OntoBDC container directory."
            )
        return project_path

    def execute_capability(self, capability: Capability) -> Dict[str, Any]:
        try:
            return CapabilityExecutor.execute(capability, self.context)
        except ValueError as error:
            raise CliCommandArgumentException(str(error)) from error
