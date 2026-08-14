from pathlib import Path
from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class ProjectCreateCommand(CliCommandPort):
    """Create an InfoBIM Project at the target path."""

    METADATA = CliCommandMetadata(
        id="project_create",
        logical_component="project",
        description="Create a new InfoBIM Project at the given path.",
        arguments=[
            {
                "accepts": ["--create"],
                "valued": True,
                "description": "Create a new InfoBIM Project at the given path.",
                "usage": "infobim project --create <path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 3 and args[0] == "project" and args[1] == "--create" and bool(str(args[2]).strip())

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args = list(self._request.command_args)
        if not (len(args) == 2 and args[0] == "--create" and bool(str(args[1]).strip())):
            return False
        resolved_path = Path(str(args[1])).expanduser().resolve()
        self._request.context.delete_parameter("dataset_path")
        self._request.context.set_parameter_value("container_path", str(resolved_path))
        self._request.context.set_parameter_value("project_path", str(resolved_path))
        return True

    def run(self) -> CommandResponse:
        from infobim.project.adapter.machine import ProjectCreateStateTransitionHandler

        return ProjectCreateStateTransitionHandler(context=self._request.context).execute()
