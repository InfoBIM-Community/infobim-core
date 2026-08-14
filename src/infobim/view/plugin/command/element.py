from pathlib import Path
from typing import Dict, List, Optional

from infobim.project.plugin.command.base import ProjectBaseCommand
from infobim.view.adapter.html import WorkStream5W2HHtmlRenderer
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.storage import get_storage_file


class ViewElementCommand(ProjectBaseCommand, CliCommandPort):
    """Declare the element-view command surface."""

    METADATA = CliCommandMetadata(
        id="element",
        logical_component="view",
        description="Generate a view for one project element instance.",
        arguments=[
            {
                "accepts": ["--project", "--project-id"],
                "valued": True,
                "description": "Select the active InfoBIM project.",
                "usage": (
                    "infobim view --project <project_id> "
                    "--element <element>"
                ),
            },
            {
                "accepts": ["--element"],
                "valued": True,
                "description": "Select the element instance to render.",
                "usage": (
                    "infobim view --project <project_id> "
                    "--element <element>"
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 5
            and args[0] == "view"
            and any(flag in args for flag in ("--project", "--project-id"))
            and "--element" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        project_id: Optional[str] = self._context_value("project_id")
        element: Optional[str] = self._flag_value("--element")
        if not project_id or not element:
            return False

        self._request.context.set_parameter_value("element", element)
        return True

    def run(self) -> CommandResponse:
        root_path = Path(self._request.context.root_path).expanduser().resolve()
        project_id = str(
            self._request.context.get_parameter_value("project_id")
        ).strip()
        element_id = str(
            self._request.context.get_parameter_value("element")
        ).strip()
        storage_file = Path(
            get_storage_file(root_path=str(root_path))
        ).expanduser().resolve()
        if not storage_file.is_file():
            return ExceptionCommandResponse(
                title="Element View",
                description="Could not locate the storage index.",
                content={
                    "project_id": project_id,
                    "element": element_id,
                    "storage_file": str(storage_file),
                },
            )

        project_record = next(
            (
                item
                for item in self._list_projects(storage_file)
                if str(item.get("project_id", "")).strip() == project_id
            ),
            None,
        )
        if project_record is None:
            return ExceptionCommandResponse(
                title="Element View",
                description="The requested active InfoBIM project was not found.",
                content={
                    "project_id": project_id,
                    "element": element_id,
                },
            )

        output_file = WorkStream5W2HHtmlRenderer().render(
            project_record,
            element_id,
        )
        content: Dict[str, str] = {
            "project_id": project_id,
            "element": element_id,
            "entity": "WorkStream",
            "output_file": str(output_file),
        }
        return CommandResponse(
            title="WorkStream 5W2H View",
            description="Generated and opened the live WorkStream 5W2H view.",
            content=content,
        )

    def _flag_value(self, flag: str) -> Optional[str]:
        args: List[str] = list(self._request.command_args)
        if flag not in args:
            return None

        index: int = args.index(flag)
        if index + 1 >= len(args):
            return None

        value: str = str(args[index + 1]).strip()
        return value or None

    def _context_value(self, key: str) -> Optional[str]:
        value: object = self._request.context.get_parameter_value(key)
        if value is None:
            return None

        normalized: str = str(value).strip()
        return normalized or None
