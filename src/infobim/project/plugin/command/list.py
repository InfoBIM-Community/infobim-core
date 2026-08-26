from pathlib import Path
from typing import Any, Dict, List

from infobim.project.plugin.parameter.project import ProjectIdStrategy
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class ProjectListCommand(CliCommandPort):
    """List registered OntoBDC containers that satisfy the InfoBIM Project contract."""

    METADATA = CliCommandMetadata(
        id="project_list",
        logical_component="project",
        description="List registered InfoBIM Projects.",
        arguments=[
            {
                "accepts": ["--list", "-l"],
                "description": "List registered InfoBIM Projects.",
                "usage": "infobim project --list",
            }
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return args in (
            ["project"],
            ["project", "--list"],
            ["project", "-l"],
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return list(self._request.command_args) in (
            [],
            ["--list"],
            ["-l"],
        )

    def run(self) -> CommandResponse:
        # Imported here, not at module level -- see the identical note in
        # context/plugin/command/entity.py.
        from ontobdc.storage.plugin.command.base import StorageBaseCommand

        proxy_request = CliCommandRequest(
            logical_component="storage",
            component_action=StorageBaseCommand.METADATA.id,
            command_args=["--list"],
            context=self._request.context,
        )
        proxy = StorageBaseCommand(proxy_request)
        if not proxy.check():
            raise ValueError("Underlying OntoBDC storage list command rejected the request.")
        response = proxy.run()

        raw_containers = (
            response.content.get("containers", [])
            if isinstance(response.content, dict)
            else []
        )

        # Not every registered OntoBDC container is an InfoBIM Project --
        # only those carrying a valid reserved IfcProject dataset qualify;
        # everything else is silently excluded from this listing.
        projects: List[Dict[str, Any]] = []
        for container in raw_containers:
            container_path = str(container.get("location") or "").strip()
            if not container_path:
                continue
            project_id = ProjectIdStrategy._project_id_for_container(Path(container_path))
            if project_id is None:
                continue

            projects.append(
                {
                    "project_id": project_id,
                    "container_id": str(container.get("id") or "").strip(),
                    "project_path": container_path,
                }
            )

        return CommandResponse(
            title="InfoBIM Projects",
            description=f"Found {len(projects)} registered InfoBIM Project(s).",
            content={"projects": projects},
        )
