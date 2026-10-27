from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Type

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.command import entity_inspect as ontobdc_entity_inspect
from ontobdc.shared.adapter.parameter import RequiredParameter

from infobim.ifc.adapter.element import IfcElementEntity
from infobim.project.adapter.proxy import ContainerCommandProxy


class ProjectEntityInspectCommand(ContainerCommandProxy):
    """
    Inspect one entity of an InfoBIM project by its global id.

    The command is OntoBDC's own container entity inspection. The entities
    of a dataset are OntoBDC's to answer, so it goes first; an entity no
    dataset keeps may be an element of an IFC model of the project, which
    is the one InfoBIM answers, the way ``infobim ifc --guid <id> --inspect``
    does.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_entity_inspect",
        logical_component="project",
        description="Inspect one entity of an InfoBIM Project by its global id.",
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
                for argument in ontobdc_entity_inspect.ContainerEntityInspectCommand.METADATA.arguments
                if argument["accepts"] != ["--container"]
            ],
        ],
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_entity_inspect.ContainerEntityInspectCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity inspection at the CLI routing stage.
        """
        return ProjectEntityInspectCommand.accepts_as_target(
            ProjectEntityInspectCommand.TARGET, args
        )

    def run(self) -> CommandResponse:
        """
        Inspect the entity in the datasets of the project, or else in its IFC models.
        """
        try:
            return super().run()
        except LookupError as not_kept:
            context: Any = self._request.context
            project_path: Path = Path(
                RequiredParameter.of(context, self.TARGET.CONTAINER_KEY)
            ).expanduser().resolve()
            global_id: str = RequiredParameter.of(context, self.TARGET.ENTITY_KEY)
            dataset: Optional[Dict[str, Any]] = IfcElementEntity.find(project_path, global_id)
            if dataset is None:
                raise IfcElementEntity.absent(project_path, global_id, not_kept)

            return CommandResponse(
                title="Container Entity",
                description=f"Inspect the IFC element {global_id} of the project «{project_path.name}».",
                content={"datasets": [dataset]},
            )
