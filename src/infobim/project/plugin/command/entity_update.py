from typing import ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.container.plugin.command import entity_update as ontobdc_entity_update

from infobim.project.adapter.entity_proxy import EntityRepositoryProxy


class ProjectEntityUpdateCommand(EntityRepositoryProxy):
    """
    Change the fields of an entity of an InfoBIM project.

    The command is OntoBDC's own container entity update. What InfoBIM adds
    is the project selector (``--global-id``, or the current directory),
    the check that the container is a project, and the CSV repository that
    keeps the entities of a project.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_entity_update",
        logical_component="project",
        description="Change the fields of an entity of an InfoBIM Project.",
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
                for argument in ontobdc_entity_update.ContainerEntityUpdateCommand.METADATA.arguments
                if argument["accepts"] != ["--container"]
            ],
        ],
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_entity_update.ContainerEntityUpdateCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity update at the CLI routing stage.
        """
        return ProjectEntityUpdateCommand.accepts_as_target(
            ProjectEntityUpdateCommand.TARGET, args
        )
