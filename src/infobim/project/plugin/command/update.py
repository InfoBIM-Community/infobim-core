from pathlib import Path
from typing import Dict, List, Optional

from infobim.project.plugin.capability.transformation.updated import (
    UpdatedCapability,
)
from infobim.project.plugin.command.base import ProjectBaseCommand
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.storage import get_storage_file


class ProjectUpdateCommand(ProjectBaseCommand):
    METADATA = CliCommandMetadata(
        id="update",
        logical_component="project",
        description="Update an InfoBIM project RO-Crate file inventory.",
        arguments=[
            {
                "accepts": ["--project", "--project-id"],
                "valued": True,
                "description": "Select the active InfoBIM project.",
                "usage": (
                    "infobim project --project <project_id> --update"
                ),
            },
            {
                "accepts": ["--update"],
                "valued": False,
                "description": (
                    "Synchronize the project RO-Crate with its current files."
                ),
                "usage": (
                    "infobim project --project <project_id> --update"
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 4
            and args[0] == "project"
            and any(flag in args for flag in ("--project", "--project-id"))
            and "--update" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        project_id = self._flag_value("--project", "--project-id")
        if not project_id:
            return False

        root_path = Path(
            self._request.context.root_path
        ).expanduser().resolve()
        storage_file = Path(
            get_storage_file(root_path=str(root_path))
        ).expanduser().resolve()
        if not storage_file.is_file():
            return False

        project_record: Optional[Dict[str, str]] = next(
            (
                item
                for item in self._list_projects(storage_file)
                if str(item.get("project_id", "")).strip() == project_id
            ),
            None,
        )
        if project_record is None:
            return False

        self._request.context.set_parameter_value(
            "project_id",
            project_id,
        )
        self._request.context.set_parameter_value(
            "container_path",
            str(project_record["path"]).strip(),
        )
        return True

    def run(self) -> CommandResponse:
        project_id = str(
            self._request.context.get_parameter_value("project_id")
        ).strip()
        container_path = str(
            self._request.context.get_parameter_value("container_path")
        ).strip()

        try:
            result = UpdatedCapability().execute(self._request.context)
        except Exception as error:
            return ExceptionCommandResponse(
                title="Project Update",
                description="Failed to update the InfoBIM project.",
                content={
                    "project_id": project_id,
                    "path": container_path,
                    "error": str(error),
                },
            )

        return CommandResponse(
            title="InfoBIM Project Updated",
            description=(
                "The project RO-Crate now reflects the current file inventory."
            ),
            content={
                "project_id": project_id,
                "path": container_path,
                "crate_file": str(result.get("crate_file", "")).strip(),
            },
        )

    def _flag_value(self, *flags: str) -> Optional[str]:
        args = list(self._request.command_args)
        for flag in flags:
            if flag not in args:
                continue
            index = args.index(flag)
            if index + 1 >= len(args):
                continue
            value = str(args[index + 1]).strip()
            if value:
                return value
        return None
