from typing import ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.container.plugin.command import entity_create as ontobdc_entity_create

from infobim.project.adapter.entity_proxy import EntityRepositoryProxy


class ProjectEntityCreateCommand(EntityRepositoryProxy):
    """
    Create an instance of an entity in an InfoBIM project.

    The command is OntoBDC's own container entity creation. What InfoBIM adds
    is the project selector (``--global-id``, or the current directory),
    the check that the container is a project, and the CSV repository that
    keeps the entities of a project.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_entity_create",
        logical_component="project",
        description="Create an instance of an entity in an InfoBIM Project.",
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
                for argument in ontobdc_entity_create.ContainerEntityCreateCommand.METADATA.arguments
                if argument["accepts"] != ["--container"]
            ],
        ],
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_entity_create.ContainerEntityCreateCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity creation at the CLI routing stage.
        """
        return ProjectEntityCreateCommand.accepts_as_target(
            ProjectEntityCreateCommand.TARGET, args
        )
