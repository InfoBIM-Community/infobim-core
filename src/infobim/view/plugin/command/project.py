from pathlib import Path
from typing import Dict, List, Optional

from infobim.project.plugin.command.base import ProjectBaseCommand
from infobim.view.adapter.html import ProjectDashboardHtmlRenderer
from ontobdc.cli.domain.port.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.storage import get_storage_file


class ViewProjectCommand(ProjectBaseCommand):
    METADATA = CliCommandMetadata(
        id="project",
        logical_component="view",
        description="Generate and open the HTML dashboard for an active InfoBIM project.",
        arguments=[
            {
                "accepts": ["--project-id"],
                "valued": True,
                "description": "Generate the project dashboard for the given project identifier.",
                "usage": "infobim view --project-id <project_id>",
            }
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 3
            and args[0] == "view"
            and args[1] == "--project-id"
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        project_id: Optional[str] = self._get_flag_value("--project-id")
        if not project_id:
            return False

        self._request.context.set_parameter_value("project_id", project_id)
        return True

    def run(self) -> CommandResponse:
        root_path: Path = Path(self._request.context.root_path).expanduser().resolve()
        storage_file: Path = Path(get_storage_file(root_path=str(root_path))).expanduser().resolve()
        project_id: str = str(self._request.context.get_parameter_value("project_id")).strip()

        if not storage_file.is_file():
            return ExceptionCommandResponse(
                title="Project View",
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
                title="Project View",
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
                title="Project View",
                description="The requested active InfoBIM project was not found.",
                content={
                    "project_id": project_id,
                    "root_path": str(root_path),
                },
            )

        renderer: ProjectDashboardHtmlRenderer = ProjectDashboardHtmlRenderer()
        output_file: Path = renderer.render(project_record)

        return CommandResponse(
            title="Project View",
            description="Generated and opened the InfoBIM project dashboard.",
            content={
                "project_id": str(project_record.get("project_id", "")).strip(),
                "name": str(project_record.get("name", "")).strip(),
                "path": str(project_record.get("path", "")).strip(),
                "output_file": str(output_file),
            },
        )

    def _get_flag_value(self, flag_name: str) -> Optional[str]:
        args: List[str] = list(self._request.command_args)
        if flag_name in args:
            index: int = args.index(flag_name)
            if index + 1 >= len(args):
                return None

            value: str = str(args[index + 1]).strip()
            if value:
                return value

        context_value: object = self._request.context.get_parameter_value("project_id")
        if context_value is None:
            return None

        resolved_value: str = str(context_value).strip()
        return resolved_value or None
