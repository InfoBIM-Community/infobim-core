from typing import List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.container.plugin.command.dataset import (
    ContainerCreateDatasetCommand,
)

from infobim.project.adapter.proxy import ContainerCommandProxy


class ProjectCreateDatasetCommand(ContainerCommandProxy):
    """
    Creates a dataset inside a project, which is inside its container.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_create_dataset",
        logical_component="project",
        description="Create a new dataset inside a selected InfoBIM Project.",
        arguments=[
            {
                "accepts": [
                    "--global-id",
                ],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select the project that will hold the new dataset, "
                    "by the GlobalId carried by its IfcProject or by the "
                    "container storage identifier. The dataset is created "
                    "as a subfolder of the project container with its "
                    "own metadata, title and index entry; its title is "
                    "given alongside --create-dataset."
                ),
                "type": "str",
            },
            {
                "accepts": ["--create-dataset"],
                "valued": True,
                "description": (
                    "Title of the new dataset to create inside the "
                    "selected project. When --global-id is omitted the "
                    "project is resolved from the current working "
                    "directory."
                ),
                "type": "str",
            },
        ],
    )

    TARGET = ContainerCreateDatasetCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the dataset creation at the CLI routing stage.
        """
        target: Type[CliCommandPort] = ProjectCreateDatasetCommand.TARGET

        return ContainerCommandProxy.accepts_as_target(target, args)
