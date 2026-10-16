from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.context.plugin.command import entity as _ontobdc_entity

from infobim.context.plugin.machine.entity_inspection.machine import EntityInspectionStateTransitionHandler


class ContextEntityInspectCommand(_ontobdc_entity.ContextEntityInspectCommand):
    """
    Expose ``ontobdc context --entity [<iri>] --inspect`` as ``infobim context``.

    The entity is resolved by InfoBIM's own inspection machine, which turns
    an IFC class name into its IFC4 ifcOWL URI.
    """

    def run(self) -> CommandResponse:
        return EntityInspectionStateTransitionHandler(context=self._request.context).execute()
