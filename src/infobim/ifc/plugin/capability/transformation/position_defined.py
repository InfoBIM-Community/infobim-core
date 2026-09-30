import math
from typing import Any, ClassVar, Dict, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import PositionDefinitionInvalidError
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class PositionDefinedCapability(TransactionCapability):
    """
    Defines where the geometry will be placed, before it is created.

    Position is not a dimension: the primitive's own measurements say how
    big it is, and this says where it sits. Three axes are read, and each
    one is read the same way — stated by this run and a real number, or
    not stated at all.

    A coordinate that was stated has to be a number a placement can be
    made of: something that does not read as a number, and something that
    reads as NaN or as an infinity, are reported rather than rounded off.
    A coordinate nobody stated is the origin on that axis. That zero is
    the contract of the state and not a value invented to cover an
    absence: placing at the origin is what "no position was given" means
    here, so ``x`` alone places the product on the X axis instead of
    failing for the two axes the caller had no opinion about.

    Only an axis this invocation actually named counts. The CLI context
    outlives a command, and a coordinate written down by an earlier run
    is not this run's answer — which matters exactly because this is a
    fact of the run: the position it defines is bound as an object, which
    the context keeps in memory and never writes to ``context.ttl``, so a
    process that starts again finds it undefined and defines it again.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "position_defined"
        ),
        version="0.1.0",
        name="Position Defined",
        description="Define the position the geometric operation requires.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "position_defined"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "x": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Coordinate along the X axis; the origin when it is "
                        "not stated."
                    ),
                },
                "y": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Coordinate along the Y axis; the origin when it is "
                        "not stated."
                    ),
                },
                "z": {
                    "type": "number",
                    "required": False,
                    "description": (
                        "Coordinate along the Z axis; the origin when it is "
                        "not stated."
                    ),
                },
            },
        },
        log_message={
            "info": {
                "en": "The position of the geometric operation is defined.",
            },
            "debug_entry": {
                "en": "Defining the position of the geometric operation.",
            },
        },
    )

    AXES: ClassVar[Tuple[str, ...]] = ("x", "y", "z")
    FLAG_PREFIX: ClassVar[str] = "--"
    POSITION_KEY: ClassVar[str] = "position"
    ORIGIN_COORDINATE: ClassVar[float] = 0.0
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"

    def label(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.POSITION_DEFINED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.POSITION_DEFINED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Bind the position this run places the geometry at.
        """
        position: Dict[str, float] = {
            axis: self._coordinate(context, axis) for axis in self.AXES
        }
        context.set_parameter_value(self.POSITION_KEY, position)

        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductCreateProcessState.POSITION_DEFINED
            ),
            self.POSITION_KEY: position,
        }

    @classmethod
    def _coordinate(cls, context: CliContextPort, axis: str) -> float:
        """
        Return the coordinate this run states for an axis, or the origin.
        """
        flag: str = f"{cls.FLAG_PREFIX}{axis}"
        if flag in context.raw_args:
            stated: Any = context.get_parameter_value(axis)
            if stated is None:
                return cls.ORIGIN_COORDINATE
            return cls._real_number(axis, stated)

        if context.has_parameter(axis):
            stated = context.get_parameter_value(axis)
            if stated is None:
                return cls.ORIGIN_COORDINATE
            return cls._real_number(axis, stated)

        return cls.ORIGIN_COORDINATE

    @classmethod
    def _real_number(cls, axis: str, stated: Any) -> float:
        """
        Return the stated coordinate as a real number, or fail saying why not.
        """
        if isinstance(stated, bool):
            raise PositionDefinitionInvalidError(
                f"The {axis} coordinate is {stated}, which is not a number a "
                f"position can be made of."
            )

        if isinstance(stated, (int, float)):
            coordinate: float = float(stated)
        elif isinstance(stated, str) and stated.strip():
            try:
                coordinate = float(stated.strip())
            except ValueError as error:
                raise PositionDefinitionInvalidError(
                    f"The {axis} coordinate is '{stated}', which does not "
                    f"read as a number."
                ) from error
        else:
            raise PositionDefinitionInvalidError(
                f"The {axis} coordinate was stated as {stated!r}, which does "
                f"not read as a number."
            )

        if not math.isfinite(coordinate):
            raise PositionDefinitionInvalidError(
                f"The {axis} coordinate is {coordinate}, and a position "
                f"cannot be placed at a value that is not finite."
            )

        return coordinate
