import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from infobim.project.plugin.command.base import ProjectBaseCommand
from infobim.shared.adapter.entity_workbook import (
    EntityWorkbookAdapter,
    EntityWorkbookArtifact,
    EntityWorkbookField,
)
from infobim.shared.adapter.entity_linkset import (
    EntityLinksetAdapter,
    EntityLinksetArtifact,
    EntityLinksetField,
)
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.storage import get_storage_file


class ProjectCreateElementCommand(CliCommandPort):
    """Declare the project entity-instantiation command surface."""

    METADATA = CliCommandMetadata(
        id="project_create_element",
        logical_component="project",
        description="Create a named element as an instance of an entity class.",
        arguments=[
            {
                "accepts": ["--project", "--project-id"],
                "valued": True,
                "description": "Select the active InfoBIM project.",
                "usage": (
                    "infobim project --project <project_id> "
                    "--entity <entity_class> --create <name>"
                ),
            },
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": "Select the entity class to instantiate.",
                "usage": (
                    "infobim project --project <project_id> "
                    "--entity <entity_class> --create <name>"
                ),
            },
            {
                "accepts": ["--create"],
                "valued": True,
                "description": "Set the initial name of the new element.",
                "usage": (
                    "infobim project --project <project_id> "
                    "--entity <entity_class> --create <name>"
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 7
            and args[0] == "project"
            and any(flag in args for flag in ("--project", "--project-id"))
            and "--entity" in args
            and "--create" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        project_id: Optional[str] = self._context_value("project_id")
        entity: Optional[str] = self._flag_value("--entity")
        element_name: Optional[str] = self._flag_value("--create")
        if not project_id or not entity or not element_name:
            return False
        if not self._is_work_stream(entity):
            return False

        container_path: Optional[Path] = self._resolve_project_path(project_id)
        if container_path is None:
            return False

        self._request.context.set_parameter_value("entity", entity)
        self._request.context.set_parameter_value("element_name", element_name)
        self._request.context.set_parameter_value(
            "container_path",
            str(container_path),
        )
        return True

    def run(self) -> CommandResponse:
        project_id: str = str(
            self._request.context.get_parameter_value("project_id")
        )
        element_name: str = str(
            self._request.context.get_parameter_value("element_name")
        )
        container_path = Path(
            str(self._request.context.get_parameter_value("container_path"))
        ).expanduser().resolve()
        output_dir: Path = container_path / "payload" / "document"
        workbook_path: Path = output_dir / "workstreams.xlsx"
        fields: List[EntityWorkbookField] = self._work_stream_fields()
        adapter = EntityWorkbookAdapter()
        records: List[Dict[str, Any]] = adapter.read(
            workbook_path=workbook_path,
            worksheet_name="WorkStream",
            fields=fields,
        )
        global_id: str = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"urn:infobim:project:{project_id}:workstream:{element_name}",
            )
        )
        if not any(
            str(record.get("GlobalId") or "").strip() == global_id
            for record in records
        ):
            records.append(
                {
                    "GlobalId": global_id,
                    "Name": element_name,
                    "Description": "",
                    "What": "",
                    "Why": "",
                    "Who": "",
                    "Where": "",
                    "When": "",
                    "How": "",
                    "HowMuch": "",
                }
            )

        artifact: EntityWorkbookArtifact = adapter.generate(
            output_dir=output_dir,
            workbook_name=workbook_path.name,
            worksheet_name="WorkStream",
            fields=fields,
            records=records,
            datapackage_path=container_path / ".__ontobdc__" / "datapackage.json",
            package_name="infobim_project",
            resource_name="work_stream",
            primary_key=["GlobalId"],
        )
        linkset_artifact: EntityLinksetArtifact = EntityLinksetAdapter().generate(
            container_path=container_path,
            workbook_path=artifact.workbook_path,
            worksheet_name=artifact.worksheet_name,
            entity_name="WorkStream",
            facade_uri=(
                "http://datacenter.app.br/ontology/productivity/entity/"
                "work_stream/facade.ttl#WorkStreamFacade"
            ),
            fields=[
                EntityLinksetField(
                    name=field.name,
                    facade_field_uri=(
                        "http://datacenter.app.br/ontology/productivity/entity/"
                        f"work_stream/facade.ttl#{field.name}Field"
                    ),
                )
                for field in fields
            ],
        )

        content: Dict[str, Any] = {
            "project_id": project_id,
            "entity": str(self._request.context.get_parameter_value("entity")),
            "element_id": global_id,
            "element_name": element_name,
            "workbook_path": str(artifact.workbook_path),
            "datapackage_path": str(artifact.datapackage_path),
            "linkset_path": str(linkset_artifact.linkset_path),
            "link_count": linkset_artifact.link_count,
            "work_stream_count": artifact.generated_row_count,
        }
        return CommandResponse(
            title="Project Element Creation",
            description="Created the WorkStream entry and generated its project workbook.",
            content=content,
        )

    def _work_stream_fields(self) -> List[EntityWorkbookField]:
        return [
            EntityWorkbookField("GlobalId"),
            EntityWorkbookField("Name"),
            EntityWorkbookField("Description"),
            EntityWorkbookField("What"),
            EntityWorkbookField("Why"),
            EntityWorkbookField("Who"),
            EntityWorkbookField("Where"),
            EntityWorkbookField("When"),
            EntityWorkbookField("How"),
            EntityWorkbookField("HowMuch"),
        ]

    def _resolve_project_path(self, project_id: str) -> Optional[Path]:
        root_path: Path = Path(
            self._request.context.root_path
        ).expanduser().resolve()
        storage_file: Path = Path(
            get_storage_file(root_path=str(root_path))
        ).expanduser().resolve()
        if not storage_file.is_file():
            return None

        project_record: Optional[Dict[str, str]] = next(
            (
                item
                for item in ProjectBaseCommand(
                    self._request
                )._list_projects(storage_file)
                if str(item.get("project_id", "")).strip() == project_id
            ),
            None,
        )
        if project_record is None:
            return None

        return Path(str(project_record["path"])).expanduser().resolve()

    def _is_work_stream(self, entity: str) -> bool:
        normalized: str = entity.strip().lower().replace("_", "")
        return normalized == "workstream" or normalized.endswith("#workstream")

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
