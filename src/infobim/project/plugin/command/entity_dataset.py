from typing import ClassVar, List, Type

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.container.plugin.command import entity_dataset as ontobdc_entity_dataset

from infobim.project.adapter.proxy import ContainerCommandProxy


class ProjectEntityDatasetCommand(ContainerCommandProxy):
    """
    Make sure an InfoBIM project has a dataset for an entity type.

    The command is OntoBDC's own container entity dataset. What InfoBIM adds
    is the project selector (``--global-id``, or the current directory) and
    the check that the container is a project.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_entity_dataset",
        logical_component="project",
        description="Make sure an InfoBIM Project has a dataset for an entity type.",
        arguments=[
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select the project by the GlobalId carried by its "
                    "IfcProject or by the container storage identifier. "
                    "When omitted, resolve the project from the current "
                    "working directory."
                ),
                "type": "str",
            },
            *[
                argument
                for argument in ontobdc_entity_dataset.ContainerEntityDatasetCommand.METADATA.arguments
                if argument["accepts"] != ["--container"]
            ],
        ],
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_entity_dataset.ContainerEntityDatasetCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the dataset of an entity at the CLI routing stage.
        """
        return ProjectEntityDatasetCommand.accepts_as_target(
            ProjectEntityDatasetCommand.TARGET, args
        )
