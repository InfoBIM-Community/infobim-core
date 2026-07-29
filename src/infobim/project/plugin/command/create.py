from typing import List

from infobim.shared.adapter.path import CliPathAdapter
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class StorageCreateCommand(CliCommandPort):
    """
    Command for creating a new local InfoBIM storage container at the given path.
    """

    METADATA = CliCommandMetadata(
        id="proj_create",
        logical_component="project",
        description="Create a new local InfoBIM project container at the given path.",
        arguments=[
            {
                "accepts": [
                    "--create",
                ],
                "valued": True,
                "description": "Create a new local InfoBIM project container at the given path.",
                "usage": "infobim project --create <path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return len(args) > 2 and args[0] == "project" and args[1] == "--create"

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._path_adapter: CliPathAdapter = CliPathAdapter()

    def check(self) -> bool:
        if not (
            len(self._request.command_args) == 2
            and self._request.command_args[0] == "--create"
        ):
            return False

        resolved_path = self._path_adapter.resolve(self._request.command_args[1])
        self._request.context.delete_parameter("dataset_path")
        self._request.context.set_parameter_value("container_path", str(resolved_path))

        return True

    def run(self) -> CommandResponse:
        from infobim.project.adapter.machine import ContainerCreateStateTransitionHandler

        handler = ContainerCreateStateTransitionHandler(
            context=self._request.context,
        )

        return handler.execute()
