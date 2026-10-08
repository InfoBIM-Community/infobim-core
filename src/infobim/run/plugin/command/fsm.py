from typing import Any, ClassVar, List, Type

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import RunCommandResponse
from ontobdc.run.plugin.command import fsm as ontobdc_fsm

from infobim.annotation.adapter.csv_repository import AnnotationCsvRepository
from infobim.project.adapter.proxy import ContainerCommandProxy


class InfoBimRunFsmCommand(ContainerCommandProxy):
    """
    Run a finite state machine on an InfoBIM project.

    The command is OntoBDC's own ``run --fsm``. What InfoBIM adds is the
    project selector (``--global-id``, or the current directory), the check
    that the container is a project, and the CSV repository that keeps the
    entities of a project (its annotations), handed to the machine through
    the context for the machines that write or read entities.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="fsm",
        logical_component="run",
        description="Run a finite state machine on an InfoBIM project, from the YAML of its statechart.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select the project by the GlobalId carried by its "
                    "IfcProject. When omitted, resolve the project from the "
                    "current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": ["--fsm"],
                "valued": True,
                "parameter": "fsm_path",
                "description": (
                    "Path of the statechart YAML of the machine to run, or its "
                    "path inside an installed package."
                ),
                "type": "Path",
                "usage": (
                    "infobim run --fsm <yaml> [--global-id <project-global-id>] "
                    "[--<parameter-name> <value>]..."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "run"
    TARGET_COMPONENT: ClassVar[str] = "run"
    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_fsm.RunFsmCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the run of a machine at the CLI routing stage.
        """
        return InfoBimRunFsmCommand.accepts_as_target(
            InfoBimRunFsmCommand.TARGET, args
        )

    def run(self) -> RunCommandResponse:
        """
        Hand the machine the repository of the entities, and run it.
        """
        context: Any = self._request.context
        context.set_parameter_value("entity_repository", AnnotationCsvRepository())
        try:
            return self._target.run()
        finally:
            context.delete_parameter("entity_repository")
