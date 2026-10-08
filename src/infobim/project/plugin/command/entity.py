from typing import ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.container.plugin.command import entity as ontobdc_entity

from infobim.project.adapter.proxy import ContainerCommandProxy


class ProjectEntityCommand(ContainerCommandProxy):
    """
    List the entities of an InfoBIM project, dataset by dataset.

    The command is OntoBDC's own container entity listing. What InfoBIM adds
    is the project selector (``--global-id``, or the current directory) and
    the check that the container is a project.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_entity",
        logical_component="project",
        description="List the entities of an InfoBIM Project.",
        arguments=[
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select which project to list, by the GlobalId carried "
                    "by its IfcProject or by the container storage "
                    "identifier. When omitted, resolve the project from the "
                    "current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": ["--entity"],
                "description": (
                    "List every entity the project holds, grouped by the "
                    "dataset of the container that keeps it."
                ),
            },
        ],
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_entity.ContainerEntityCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity listing at the CLI routing stage.
        """
        return ProjectEntityCommand.accepts_as_target(
            ProjectEntityCommand.TARGET, args
        )
