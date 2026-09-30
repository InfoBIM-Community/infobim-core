import math
from typing import Any, ClassVar, Dict, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import DisplacementDefinitionInvalidError
from infobim.ifc.plugin.machine.ifc_element_move.state import (
    IfcElementMoveContextKeys,
    IfcElementMoveProcessState,
)


class DisplacementDefinedCapability(TransactionCapability):
    """
    Turns the axis and the amount this run names into a displacement vector.

    The vector carries the stated amount on the named axis and zero on
    the other two, the same way ``PositionDefinedCapability`` reads an
    unstated axis as the origin: what this run did not name is an axis
    it moves nothing along, not an axis whose value was forgotten.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "displacement_defined"
        ),
        version="0.1.0",
        name="Displacement Defined",
        description="Define the displacement vector this run moves the element by.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "displacement_defined"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "axis": {
                    "type": "string",
                    "required": True,
                    "description": "Axis to move the element along: x, y or z.",
                },
                "amount": {
                    "type": "string",
                    "required": True,
                    "description": "Distance to move along the given axis.",
                },
            },
            "required": ["axis", "amount"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "displacement": {"type": "object"},
            },
            "required": ["displacement"],
        },
        log_message={
            "info": {
                "en": "The displacement this run moves the element by is defined.",
            },
            "debug_entry": {
                "en": "Defining the displacement this run moves the element by.",
            },
        },
    )

    AXES: ClassVar[Tuple[str, str, str]] = ("x", "y", "z")
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    DISPLACEMENT_KEY: ClassVar[str] = "displacement"

    def label(self, lang: str = "en") -> str:
        return IfcElementMoveProcessState.DISPLACEMENT_DEFINED.label(lang)

    def description(self, lang: str = "en") -> str:
        return IfcElementMoveProcessState.DISPLACEMENT_DEFINED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        axis: str = self._axis(context)
        amount: float = self._amount(context)

        displacement: Dict[str, float] = {
            candidate: (amount if candidate == axis else 0.0)
            for candidate in self.AXES
        }
        context.set_parameter_value(
            IfcElementMoveContextKeys.DISPLACEMENT_KEY,
            displacement,
        )

        return {
            self.RESULTING_STATE_KEY: (
                IfcElementMoveProcessState.DISPLACEMENT_DEFINED
            ),
            self.DISPLACEMENT_KEY: displacement,
        }

    @classmethod
    def _axis(cls, context: CliContextPort) -> str:
        axis: str = RequiredParameter.of(
            context,
            IfcElementMoveContextKeys.AXIS_KEY,
        ).lower()
        if axis not in cls.AXES:
            raise DisplacementDefinitionInvalidError(
                f"The axis '{axis}' is not one of {cls.AXES}."
            )

        return axis

    @staticmethod
    def _amount(context: CliContextPort) -> float:
        raw: Any = context.get_parameter_value(
            IfcElementMoveContextKeys.AMOUNT_KEY
        )
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            raise DisplacementDefinitionInvalidError(
                f"The amount {raw!r} is not a number."
            )

        try:
            amount: float = float(raw)
        except (TypeError, ValueError) as error:
            raise DisplacementDefinitionInvalidError(
                f"The amount {raw!r} does not read as a number."
            ) from error

        if not math.isfinite(amount) or amount == 0.0:
            raise DisplacementDefinitionInvalidError(
                f"The amount must be finite and non-zero; got {amount}."
            )

        return amount
