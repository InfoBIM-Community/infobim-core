from typing import List

from infobim.project.plugin.parameter.project import ProjectIdStrategy
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class ProjectDeleteCommand(CliCommandPort):
    """Remove an InfoBIM Project from the OntoBDC storage index."""

    METADATA = CliCommandMetadata(
        id="project_delete",
        logical_component="project",
        description="Delete an InfoBIM Project from the underlying OntoBDC storage index.",
        arguments=[
            {
                "accepts": ["--delete"],
                "valued": True,
                "description": "Delete the Project selected by IfcProject GlobalId.",
                "usage": "infobim project --delete <GlobalId>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) == 3 and args[0] == "project" and args[1] == "--delete" and bool(str(args[2]).strip())

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        args = list(self._request.command_args)
        if not (len(args) == 2 and args[0] == "--delete" and bool(str(args[1]).strip())):
            return False
        self._request.context.set_parameter_value("project_id", str(args[1]).strip())
        ProjectIdStrategy().execute(self._request.context)
        return bool(str(self._request.context.get_parameter_value("container_id") or "").strip())

    def run(self) -> CommandResponse:
        # Imported here, not at module level -- see the identical note in
        # context/plugin/command/entity.py.
        from ontobdc.storage.plugin.command.container.delete import StorageDeleteCommand

        project_id = str(self._request.command_args[1]).strip()
        container_id = str(self._request.context.get_parameter_value("container_id") or "").strip()
        proxy_request = CliCommandRequest(
            logical_component="storage",
            component_action=StorageDeleteCommand.METADATA.id,
            command_args=["--delete", container_id],
            context=self._request.context,
        )
        proxy = StorageDeleteCommand(proxy_request)
        if not proxy.check():
            raise ValueError("Underlying OntoBDC delete command rejected the resolved container.")

        response = proxy.run()
        if response.title == "Container Deleted":
            response.title = "InfoBIM Project Deleted"
        else:
            response.title = "Failed to Delete InfoBIM Project"
        if isinstance(response.content, dict):
            response.content["project_id"] = project_id
        return response
