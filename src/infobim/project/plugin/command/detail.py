from pathlib import Path
from typing import Dict, List, Optional

from infobim.project.plugin.command.base import ProjectBaseCommand
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import ExceptionCommandResponse, ListCommandResponse
from ontobdc.storage import get_storage_file


class ProjectDetailCommand(ProjectBaseCommand):
    METADATA = CliCommandMetadata(
        id="detail",
        logical_component="project",
        description="Show details for a single active InfoBIM project.",
        arguments=[
            {
                "accepts": ["--project", "--project-id"],
                "valued": True,
                "description": "Show the active project matching the given project identifier.",
                "usage": "infobim project --project <project_id>",
            }
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 3
            and args[0] == "project"
            and args[1] in ("--project", "--project-id")
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        project_id: Optional[str] = self._get_project_id()
        if not project_id:
            return False

        self._request.context.set_parameter_value("project_id", project_id)
        return True

    def run(self) -> ListCommandResponse | ExceptionCommandResponse:
        root_path: Path = Path(self._request.context.root_path).expanduser().resolve()
        storage_file: Path = Path(get_storage_file(root_path=str(root_path))).expanduser().resolve()
        project_id: str = str(self._request.context.get_parameter_value("project_id")).strip()

        if not storage_file.is_file():
            return ExceptionCommandResponse(
                title="Project Detail",
                description="Could not locate the storage index for the current workspace.",
                content={
                    "root_path": str(root_path),
                    "storage_file": str(storage_file),
                    "project_id": project_id,
                },
            )

        try:
            projects: List[Dict[str, str]] = self._list_projects(storage_file)
        except Exception as error:
            return ExceptionCommandResponse(
                title="Project Detail",
                description="Failed to load active InfoBIM projects.",
                content={
                    "root_path": str(root_path),
                    "storage_file": str(storage_file),
                    "project_id": project_id,
                    "error": str(error),
                },
            )

        project_record: Optional[Dict[str, str]] = next(
            (
                item
                for item in projects
                if str(item.get("project_id", "")).strip() == project_id
            ),
            None,
        )
        if project_record is None:
            return ExceptionCommandResponse(
                title="Project Detail",
                description="The requested active InfoBIM project was not found.",
                content={
                    "project_id": project_id,
                    "root_path": str(root_path),
                },
            )

        return ListCommandResponse(
            title="Active InfoBIM Project",
            description="Resolved active project in the current storage.",
            content={
                "rows": [
                    {"label": "Project ID", "value": str(project_record.get("project_id", "")).strip()},
                    {"label": "Name", "value": str(project_record.get("name", "")).strip()},
                    {"label": "Path", "value": str(project_record.get("path", "")).strip()},
                ]
            },
        )

    def _get_project_id(self) -> Optional[str]:
        context_value: object = self._request.context.get_parameter_value("project_id")
        if context_value is None:
            return None

        resolved_value: str = str(context_value).strip()
        return resolved_value or None
