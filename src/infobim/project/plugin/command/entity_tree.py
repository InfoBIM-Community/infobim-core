from typing import ClassVar, List, Type

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.container.plugin.command import entity_tree as ontobdc_entity_tree

from infobim.project.adapter.proxy import ContainerCommandProxy


class ProjectEntityTreeCommand(ContainerCommandProxy):
    """
    Show the instances of one entity type of an InfoBIM project as a tree.

    The command is OntoBDC's own container entity tree. What InfoBIM adds
    is the project selector (``--global-id``, or the current directory) and
    the check that the container is a project.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_entity_tree",
        logical_component="project",
        description="Show the instances of an entity type of an InfoBIM Project as a tree.",
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
                for argument in ontobdc_entity_tree.ContainerEntityTreeCommand.METADATA.arguments
                if argument["accepts"] != ["--container"]
            ],
        ],
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_entity_tree.ContainerEntityTreeCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity tree at the CLI routing stage.
        """
        return ProjectEntityTreeCommand.accepts_as_target(
            ProjectEntityTreeCommand.TARGET, args
        )
