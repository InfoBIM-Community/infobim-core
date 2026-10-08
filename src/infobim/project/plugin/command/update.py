from typing import List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.container.plugin.command.update import ContainerUpdateCommand

from infobim.project.adapter.proxy import ContainerCommandProxy


class ProjectUpdateCommand(ContainerCommandProxy):
    """
    Updates a project, which is updating its container.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_update",
        logical_component="project",
        description="Update a registered InfoBIM Project from a declared source.",
        arguments=[
            {
                "accepts": [
                    "--global-id",
                ],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select which project to update, by the GlobalId "
                    "carried by its IfcProject or by the container "
                    "storage identifier. When omitted, resolve the "
                    "project from the current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": [
                    "--update",
                ],
                "valued": True,
                "parameter": "update_source",
                "description": (
                    "Source of values to write into the project's "
                    "metadata and dataset fields. Accepts a path to a "
                    ".csv file, a path to a .json file, or inline "
                    "key=value assignments separated by commas."
                ),
                "type": "str",
            },
        ],
    )

    TARGET = ContainerUpdateCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the project update at the CLI routing stage.
        """
        target: Type[CliCommandPort] = ProjectUpdateCommand.TARGET

        return ContainerCommandProxy.accepts_as_target(target, args)
