from typing import List

from infobim.project.plugin.parameter.project import ProjectIdStrategy
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class ProjectUpdateCommand(CliCommandPort):
    """Update an InfoBIM Project through the underlying OntoBDC container lifecycle."""

    METADATA = CliCommandMetadata(
        id="project_update",
        logical_component="project",
        description="Update the OntoBDC container that carries an InfoBIM Project.",
        arguments=[
            {
                "accepts": ["--project-id", "--project"],
                "valued": True,
                "description": "Select a Project by IfcProject GlobalId, container selector, or path.",
                "usage": (
                    "infobim project --update | "
                    "infobim project --project-id <GlobalId> --update | "
                    "infobim project --project <selector> --update"
                ),
            },
            {
                "accepts": ["--update"],
                "description": "Run the underlying OntoBDC container update lifecycle.",
                "usage": "infobim project --update",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if args == ["project", "--update"]:
            return True
        return (
            len(args) == 4
            and args[0] == "project"
            and args[1] in {"--project-id", "--project"}
            and bool(str(args[2]).strip())
            and args[3] == "--update"
        )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args = list(self._request.command_args)
        valid = args == ["--update"] or (
            len(args) == 3
            and args[0] in {"--project-id", "--project"}
            and bool(str(args[1]).strip())
            and args[2] == "--update"
        )
        if not valid:
            return False

        ProjectIdStrategy().execute(self._request.context)
        project_id = str(self._request.context.get_parameter_value("project_id") or "").strip()
        container_id = str(self._request.context.get_parameter_value("container_id") or "").strip()
        if not project_id or not container_id:
            raise CliCommandArgumentException(
                "Unable to resolve an InfoBIM Project. Run inside a Project or provide --project-id/--project."
            )
        return True

    def run(self) -> CommandResponse:
        # Imported here, not at module level -- see the identical note in
        # context/plugin/command/entity.py.
        from ontobdc.storage.plugin.command.container.update import StorageUpdateCommand

        project_id = str(self._request.context.get_parameter_value("project_id") or "").strip()
        container_id = str(self._request.context.get_parameter_value("container_id") or "").strip()
        proxy_request = CliCommandRequest(
            logical_component="storage",
            component_action=StorageUpdateCommand.METADATA.id,
            command_args=["--container-id", container_id, "--update"],
            context=self._request.context,
        )
        proxy = StorageUpdateCommand(proxy_request)
        if not proxy.check():
            raise ValueError("Underlying OntoBDC update command rejected the resolved container.")

        response = proxy.run()
        if response.title == "Storage Container Updated":
            response.title = "InfoBIM Project Updated"
        if isinstance(response.content, dict):
            response.content["project_id"] = project_id
        return response
