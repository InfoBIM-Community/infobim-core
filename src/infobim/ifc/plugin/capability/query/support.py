from __future__ import annotations

from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import QueryCapability


class IfcProjectQueryCapability(QueryCapability):
    """Base support for read-only IFC facade queries in one Project."""

    @staticmethod
    def project_path(context: CliContextPort) -> Path:
        value: str = str(context.get_parameter_value("project_path") or "").strip()
        if not value:
            raise ValueError("'project_path' is required.")
        project_path: Path = Path(value).expanduser().resolve()
        if not project_path.is_dir():
            raise ValueError(f"InfoBIM Project directory does not exist: {project_path}")
        return project_path

    @staticmethod
    def required_text(context: CliContextPort, parameter_name: str) -> str:
        value: str = str(
            context.get_parameter_value(parameter_name) or ""
        ).strip()
        if not value:
            raise ValueError(f"'{parameter_name}' is required.")
        return value
