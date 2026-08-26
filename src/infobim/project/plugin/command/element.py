from typing import Any, Dict, List

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.storage.plugin.command.element import StorageElementCommand

from infobim.project.plugin.parameter.project import ProjectIdStrategy


class ProjectElementCommand(CliCommandPort):
    """List the facade-backed elements of an InfoBIM Project."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_element",
        logical_component="project",
        description="List elements in a selected InfoBIM Project.",
        arguments=[
            {
                "accepts": ["--project-id", "--project"],
                "valued": True,
                "description": "Select a registered Project by IfcProject GlobalId.",
                "usage": (
                    "infobim project --project <project_id> --element "
                    "[--entity <entity-uri-or-identifier>]"
                ),
            },
            {
                "accepts": ["--element"],
                "valued": False,
                "description": "List the selected Project's elements.",
                "usage": (
                    "infobim project --project <project_id> --element "
                    "[--entity <entity-uri-or-identifier>]"
                ),
            },
            {
                "accepts": ["--entity"],
                "valued": True,
                "description": (
                    "Filter elements by an entity URI or entity_identifier."
                ),
                "usage": (
                    "infobim project --project <project_id> --element "
                    "--entity <entity-uri-or-identifier>"
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        base_arguments_valid: bool = (
            len(args) >= 4
            and args[0] == "project"
            and args[1] in {"--project-id", "--project"}
            and bool(str(args[2]).strip())
            and args[3] == "--element"
        )
        if not base_arguments_valid:
            return False
        if len(args) == 4:
            return True
        return (
            len(args) == 6
            and args[4] == "--entity"
            and bool(str(args[5]).strip())
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._project_id: str = ""
        self._project_path: str = ""
        self._container_id: str = ""
        self._entity_filter: str = ""

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        base_arguments_valid: bool = (
            len(command_args) >= 3
            and command_args[0] in {"--project-id", "--project"}
            and bool(str(command_args[1]).strip())
            and command_args[2] == "--element"
        )
        filter_arguments_valid: bool = len(command_args) == 3 or (
            len(command_args) == 5
            and command_args[3] == "--entity"
            and bool(str(command_args[4]).strip())
        )
        if not base_arguments_valid or not filter_arguments_valid:
            return False

        if len(command_args) == 5:
            self._entity_filter = str(command_args[4]).strip()

        ProjectIdStrategy().execute(self._request.context)
        self._project_id = str(
            self._request.context.get_parameter_value("project_id") or ""
        ).strip()
        self._project_path = str(
            self._request.context.get_parameter_value("project_path") or ""
        ).strip()
        self._container_id = str(
            self._request.context.get_parameter_value("container_id") or ""
        ).strip()
        if (
            not self._project_id
            or not self._project_path
            or not self._container_id
        ):
            raise CliCommandArgumentException(
                "No registered InfoBIM Project matches the given "
                "--project-id/--project selector."
            )
        return True

    def run(self) -> CommandResponse:
        storage_arguments: List[str] = [
            "--container",
            self._container_id,
            "--element",
        ]
        if self._entity_filter:
            storage_arguments.extend(["--entity", self._entity_filter])

        proxy_request: CliCommandRequest = CliCommandRequest(
            logical_component="storage",
            component_action=StorageElementCommand.METADATA.id,
            command_args=storage_arguments,
            context=self._request.context,
        )
        proxy: StorageElementCommand = StorageElementCommand(proxy_request)
        if not proxy.check():
            raise CliCommandArgumentException(
                "The underlying OntoBDC element command rejected the "
                "resolved Project container."
            )

        response: CommandResponse = proxy.run()
        elements: List[Dict[str, Any]] = list(
            response.content.get("elements") or []
        )
        return CommandResponse(
            title="InfoBIM Project Element",
            description=(
                f"Listed {len(elements)} obdc:DataEntity instance(s) present "
                "in the selected InfoBIM Project."
            ),
            content={
                "project_id": self._project_id,
                "project_path": self._project_path,
                "elements": elements,
            },
        )
