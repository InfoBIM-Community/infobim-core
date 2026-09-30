from pathlib import Path
from typing import List, Optional, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.container.plugin.command.delete import ContainerDeleteCommand

from infobim.project.adapter.proxy import ContainerCommandProxy
from infobim.project.adapter.contract import ProjectGuard


class ProjectDeleteCommand(ContainerCommandProxy):
    """
    Unregisters a project, which is unregistering its container.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_delete",
        logical_component="project",
        description="Delete an InfoBIM Project from the index.",
        arguments=[
            {
                "accepts": [
                    "--global-id",
                ],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Global identifier or storage identifier of the "
                    "InfoBIM project container to unregister from the "
                    "root storage index. Only the index entry is "
                    "removed; the project files on disk are left "
                    "untouched."
                ),
            },
            {
                "accepts": [
                    "--delete",
                ],
                "valued": True,
                "description": (
                    "Storage identifier of the project to unregister. "
                    "The project is first checked against the InfoBIM "
                    "contract so a plain container cannot be removed "
                    "through this command."
                ),
            },
        ],
    )

    TARGET = ContainerDeleteCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the project deletion at the CLI routing stage.
        """
        target: Type[CliCommandPort] = ProjectDeleteCommand.TARGET

        return ContainerCommandProxy.accepts_as_target(target, args)

    def guard_project(self) -> None:
        """
        Refuse to unregister a container that is not an InfoBIM project.

        Deletion names the container by its identifier rather than selecting
        it, so the contract is checked against what the index registers for
        that identifier, not against whatever container the current
        directory resolved to.
        """
        root_path: str = self._request.context.root_path
        container_id: str = self._request.command_args[1].strip()
        location: Optional[Path] = ProjectGuard.location_of(
            container_id,
            root_path,
        )
        if location is None:
            return

        ProjectGuard.guard(location, root_path)
