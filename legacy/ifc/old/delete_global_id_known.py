from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.plugin.machine.geometric_product_delete.state import (
    GeometricProductDeleteProcessState,
)


class DeleteGlobalIdKnownCapability(TransactionCapability):
    """
    Declare the GlobalId of the element this run will delete.

    This is a run-local state: the identifier is the argument the command
    was given, validated only for shape and presence, and the answer is
    read back from the run itself, never persisted. What a later run will
    delete is what that later run is asked to delete, not what this one
    was.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "delete_global_id_known"
        ),
        version="0.1.0",
        name="Delete - GlobalId Known",
        description=(
            "Declare and shape-validate the GlobalId of the IFC element "
            "this run will delete."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "infobim",
            "ifc",
            "geometric-product-delete",
            "delete_global_id_known",
        ],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "global_id": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "The GlobalId of the IFC element to delete."
                    ),
                },
            },
        },
        log_message={
            "info": {
                "en": "The GlobalId of the element to delete is known and valid.",
            },
            "debug_entry": {
                "en": "Validating and binding the GlobalId argument for deletion.",
            },
        },
    )

    GLOBAL_ID_KEY: ClassVar[str] = "global_id"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    MIN_LENGTH: ClassVar[int] = 2
    MAX_LENGTH: ClassVar[int] = 255

    def label(self, lang: str = "en") -> str:
        return GeometricProductDeleteProcessState.GLOBAL_ID_KNOWN.label(lang)

    def description(self, lang: str = "en") -> str:
        return (
            GeometricProductDeleteProcessState.GLOBAL_ID_KNOWN.description(lang)
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw: str = RequiredParameter.of(context, self.GLOBAL_ID_KEY)
        if not isinstance(raw, str):
            raise IfcCreationError(
                "The GlobalId for deletion must be a string; got "
                f"{type(raw).__name__}."
            )

        value: str = raw.strip()
        if not value:
            raise IfcCreationError(
                "The GlobalId for deletion is empty or whitespace-only."
            )

        if not (self.MIN_LENGTH <= len(value) <= self.MAX_LENGTH):
            raise IfcCreationError(
                f"The GlobalId '{value}' does not fall inside the valid "
                f"length range of {self.MIN_LENGTH}..{self.MAX_LENGTH}."
            )

        context.set_parameter_value(self.GLOBAL_ID_KEY, value)
        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductDeleteProcessState.GLOBAL_ID_KNOWN
            ),
            self.GLOBAL_ID_KEY: value,
        }
