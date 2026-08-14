from pathlib import Path
from typing import Dict, List, Optional

from infobim.project.plugin.command.base import ProjectBaseCommand
from infobim.view.adapter.html import ProjectDashboardHtmlRenderer
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.storage import get_storage_file


class ViewProjectCommand(ProjectBaseCommand):
    METADATA = CliCommandMetadata(
        id="project",
        logical_component="view",
        description="Generate and open a visual representation of an active InfoBIM project.",
        arguments=[
            {
                "accepts": ["--project", "--project-id"],
                "valued": True,
                "description": "Select the active InfoBIM project.",
                "usage": (
                    "infobim view --project <project_id> "
                    "--representation <html|pdf> [--language <language>]"
                ),
            },
            {
                "accepts": ["--representation"],
                "valued": True,
                "description": "Select the visual representation to generate: html or pdf.",
                "usage": (
                    "infobim view --project <project_id> "
                    "--representation <html|pdf>"
                ),
            },
            {
                "accepts": ["--language"],
                "valued": True,
                "description": (
                    "Override the language resolved by the current OntoBDC context."
                ),
                "usage": (
                    "infobim view --project <project_id> "
                    "--representation html --language pt-BR"
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "view":
            return False

        valued_args = args[1:]
        if len(valued_args) % 2 != 0:
            return False

        argument_pairs = {
            valued_args[index]: valued_args[index + 1]
            for index in range(0, len(valued_args), 2)
        }
        project_value = next(
            (
                str(argument_pairs[flag]).strip()
                for flag in ("--project", "--project-id")
                if flag in argument_pairs
            ),
            "",
        )
        return bool(project_value)

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        project_id: Optional[str] = self._get_context_value("project_id")
        if not project_id:
            return False

        return bool(self._get_context_value("representation") or "html")

    def run(self) -> CommandResponse:
        root_path: Path = Path(self._request.context.root_path).expanduser().resolve()
        storage_file: Path = Path(get_storage_file(root_path=str(root_path))).expanduser().resolve()
        project_id: str = self._get_context_value("project_id") or ""
        representation: str = (
            self._get_context_value("representation") or "html"
        ).lower()
        language: str = self._get_context_value("language") or ""

        if not storage_file.is_file():
            return ExceptionCommandResponse(
                title="Project View",
                description="Could not locate the storage index for the current workspace.",
                content={
                    "root_path": str(root_path),
                    "storage_file": str(storage_file),
                    "project_id": project_id,
                    "representation": representation,
                    "language": language,
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
                    "representation": representation,
                    "language": language,
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
                    "representation": representation,
                    "language": language,
                },
            )

        if representation != "html":
            return ExceptionCommandResponse(
                title="Project View",
                description=(
                    "The requested visual representation is recognized but does "
                    "not have a renderer yet."
                ),
                content={
                    "project_id": project_id,
                    "representation": representation,
                    "language": language,
                },
            )

        renderer = ProjectDashboardHtmlRenderer()
        output_file: Path = renderer.render(project_record)

        return CommandResponse(
            title="Project View",
            description="Generated and opened the InfoBIM project view.",
            content={
                "project_id": str(project_record.get("project_id", "")).strip(),
                "name": str(project_record.get("name", "")).strip(),
                "path": str(project_record.get("path", "")).strip(),
                "representation": representation,
                "language": language,
                "output_file": str(output_file),
            },
        )

    def _get_context_value(self, parameter_name: str) -> Optional[str]:
        context_value = self._request.context.get_parameter_value(parameter_name)
        if context_value is None:
            return None

        resolved_value = str(context_value).strip()
        return resolved_value or None
