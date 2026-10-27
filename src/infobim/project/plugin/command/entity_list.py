from typing import Any, ClassVar, List, Set, Type

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.command import entity_list as ontobdc_entity_list
from ontobdc.shared.adapter.parameter import RequiredParameter

from infobim.project.adapter.proxy import ContainerCommandProxy
from infobim.project.plugin.machine.ifc_element_list.machine import (
    IfcElementListStateTransitionHandler,
)


class ProjectEntityListCommand(ContainerCommandProxy):
    """
    List the instances of one entity type in an InfoBIM project.

    The command is OntoBDC's own container entity listing, except for the
    type no dataset keeps: IfcElement, named by that word or by the IRI of
    either schema. Its instances are the elements of the
    IFC models of the project, so listing them runs a machine of InfoBIM's
    own, and any other type is handed to OntoBDC.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="project_entity_list",
        logical_component="project",
        description="List the instances of an entity type in an InfoBIM Project.",
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
                for argument in ontobdc_entity_list.ContainerEntityListCommand.METADATA.arguments
                if argument["accepts"] != ["--container"]
            ],
        ],
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_entity_list.ContainerEntityListCommand

    IFC_ELEMENT_NAME: ClassVar[str] = "ifcelement"
    IFC_ELEMENT_IRIS: ClassVar[Set[str]] = {
        "https://standards.buildingsmart.org/IFC/DEV/IFC4/FINAL/OWL#IfcElement",
        "https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#IfcElement",
    }

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity listing by type at the CLI routing stage.
        """
        return ProjectEntityListCommand.accepts_as_target(
            ProjectEntityListCommand.TARGET, args
        )

    def run(self) -> CommandResponse:
        """
        List the elements of the IFC models for IfcElement, and hand any other type to OntoBDC.
        """
        context: Any = self._request.context
        entity: str = str(RequiredParameter.of(context, self.TARGET.ENTITY_KEY))
        if entity.casefold() != self.IFC_ELEMENT_NAME and entity not in self.IFC_ELEMENT_IRIS:
            return super().run()

        return IfcElementListStateTransitionHandler(context=context).execute()
