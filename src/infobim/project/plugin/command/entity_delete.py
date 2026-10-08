from typing import ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.container.plugin.command import entity_delete as ontobdc_entity_delete

from infobim.project.adapter.entity_proxy import EntityRepositoryProxy


class ProjectEntityDeleteCommand(EntityRepositoryProxy):
    """
    Remove an entity of an InfoBIM project.

    The command is OntoBDC's own container entity delete. What InfoBIM adds
    is the project selector (``--global-id``, or the current directory),
    the check that the container is a project, and the CSV repository that
    keeps the entities of a project.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_entity_delete",
        logical_component="project",
        description="Remove an entity of an InfoBIM Project.",
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
                for argument in ontobdc_entity_delete.ContainerEntityDeleteCommand.METADATA.arguments
                if argument["accepts"] != ["--container"]
            ],
        ],
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_entity_delete.ContainerEntityDeleteCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity delete at the CLI routing stage.
        """
        return ProjectEntityDeleteCommand.accepts_as_target(
            ProjectEntityDeleteCommand.TARGET, args
        )
