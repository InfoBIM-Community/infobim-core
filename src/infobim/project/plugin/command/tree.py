from typing import Any, Dict, List

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.storage.plugin.command.container.tree import (
    StorageContainerTreeCommand,
)

from infobim.project.plugin.parameter.project import ProjectIdStrategy


class ProjectTreeCommand(CliCommandPort):
    """Show an InfoBIM Project through its underlying container tree."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_tree",
        logical_component="project",
        description=(
            "Visualize a registered InfoBIM Project and its datasets as a "
            "tree."
        ),
        arguments=[
            {
                "accepts": ["--project-id", "--project"],
                "valued": True,
                "description": "Select a registered Project by IfcProject GlobalId.",
                "usage": "infobim project --project <project_id>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 3
            and args[0] == "project"
            and args[1] in {"--project-id", "--project"}
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._project_id: str = ""
        self._container_id: str = ""

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        if not (
            len(command_args) == 2
            and command_args[0] in {"--project-id", "--project"}
            and bool(str(command_args[1]).strip())
        ):
            return False

        ProjectIdStrategy().execute(self._request.context)
        self._project_id = str(
            self._request.context.get_parameter_value("project_id") or ""
        ).strip()
        self._container_id = str(
            self._request.context.get_parameter_value("container_id") or ""
        ).strip()
        if not self._project_id or not self._container_id:
            raise CliCommandArgumentException(
                "No registered InfoBIM Project matches the given "
                "--project-id/--project selector."
            )
        return True

    def run(self) -> CommandResponse:
        proxy_request: CliCommandRequest = CliCommandRequest(
            logical_component="storage",
            component_action=StorageContainerTreeCommand.METADATA.id,
            command_args=["--container-id", self._container_id],
            context=self._request.context,
        )
        proxy: StorageContainerTreeCommand = StorageContainerTreeCommand(
            proxy_request
        )
        if not proxy.check():
            raise CliCommandArgumentException(
                "The underlying OntoBDC container command rejected the "
                "resolved Project container."
            )

        response: CommandResponse = proxy.run()
        response.title = "InfoBIM Project"
        response.description = f"Tree view of Project {self._project_id}."
        tree: Any = response.content.get("tree")
        if isinstance(tree, dict):
            typed_tree: Dict[str, Any] = tree
            typed_tree["name"] = self._project_id
        return response
