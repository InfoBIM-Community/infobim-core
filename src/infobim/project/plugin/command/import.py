from pathlib import Path
from typing import Dict, List, Optional

from infobim.context.adapter.entity import IfcRuntimeEntityAdapter
from infobim.project.plugin.command.base import ProjectBaseCommand
from infobim.shared.adapter.path import CliPathAdapter
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.storage import get_storage_file


class ProjectImportCommand(CliCommandPort):
    METADATA = CliCommandMetadata(
        id="import",
        logical_component="project",
        description="Import a file into an InfoBIM project for a resolved IFC element.",
        arguments=[
            {
                "accepts": ["--project", "--project-id"],
                "valued": True,
                "description": "Select the active project that will receive the import.",
                "usage": "infobim project --project <project_id> --element <element_uri> --import <file_path>",
            },
            {
                "accepts": ["--element"],
                "valued": True,
                "description": "Resolve an IFC element name or URI such as IfcWorkSchedule.",
                "usage": "infobim project --project <project_id> --element <element_uri> --import <file_path>",
            },
            {
                "accepts": ["--import"],
                "valued": True,
                "description": "Select the source file to be imported into the project.",
                "usage": "infobim project --project <project_id> --element <element_uri> --import <file_path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 7
            and args[0] == "project"
            and any(flag in args for flag in ("--project", "--project-id"))
            and "--element" in args
            and "--import" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._entity_adapter = IfcRuntimeEntityAdapter()
        self._path_adapter: CliPathAdapter = CliPathAdapter()

    def check(self) -> bool:
        args: List[str] = list(self._request.command_args)
        if len(args) != 6:
            return False

        argument_pairs: Dict[str, str] = {
            args[index]: args[index + 1]
            for index in range(0, len(args), 2)
        }
        raw_project_id: str = str(
            self._request.context.get_parameter_value("project_id") or ""
        ).strip()
        raw_element: str = str(argument_pairs.get("--element", "")).strip()
        raw_import_path: str = str(argument_pairs.get("--import", "")).strip()
        if not raw_project_id or not raw_element or not raw_import_path:
            raise CliCommandArgumentException(
                "Usage: infobim project --project <project_id> --element <element_uri> --import <file_path>"
            )

        resolved_import_path: Path = self._path_adapter.resolve(
            raw_import_path,
            root_path=self._request.context.root_path,
        )
        if not resolved_import_path.exists():
            raise CliCommandArgumentException(f"Invalid import path: {raw_import_path}")

        root_path: Path = Path(self._request.context.root_path).expanduser().resolve()
        storage_file: Path = Path(get_storage_file(root_path=str(root_path))).expanduser().resolve()
        if not storage_file.is_file():
            raise CliCommandArgumentException("Could not locate the storage index for the current workspace.")

        project_record: Optional[Dict[str, str]] = next(
            (
                item
                for item in ProjectBaseCommand(self._request)._list_projects(storage_file)
                if str(item.get("project_id", "")).strip() == raw_project_id
            ),
            None,
        )
        if project_record is None:
            raise CliCommandArgumentException(f"Active InfoBIM project not found: {raw_project_id}")

        resolved_entity: Dict[str, str] = self._entity_adapter.resolve(raw_element)
        self._request.context.set_parameter_value("project_id", raw_project_id)
        self._request.context.set_parameter_value("container_path", str(project_record["path"]).strip())
        self._request.context.set_parameter_value("element_name", resolved_entity["element_name"])
        self._request.context.set_parameter_value("element_uri", resolved_entity["element_uri"])
        self._request.context.set_parameter_value("entity_uri", resolved_entity["entity_uri"])
        self._request.context.set_parameter_value("import_path", str(resolved_import_path))
        return True

    def run(self) -> CommandResponse:
        from infobim.project.adapter.element import ElementImportStateTransitionHandler

        handler = ElementImportStateTransitionHandler(
            context=self._request.context,
        )

        return handler.execute()
