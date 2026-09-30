from typing import Any, ClassVar, Dict, List, Optional, Tuple
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.movement import IfcElementMover
from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.domain.port.movement import IfcElementMoverPort
from infobim.ifc.plugin.machine.ifc_element_move.state import (
    IfcElementMoveContextKeys,
    IfcElementMoveProcessState,
)


class ElementMovedCapability(TransactionCapability):
    """
    Adds the run's displacement to the element's own placement.

    What moves is exactly the point ``IfcProductAssembler`` locates every
    element's own placement at, and nothing else: the representation the
    element carries is untouched, because every measurement in it is
    already taken from that same point. Moving an element twice moves it
    twice, since what is added is a displacement and not a position.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "element_moved"
        ),
        version="0.1.0",
        name="Element Moved",
        description="Add the run's displacement to the element's own placement.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "element_moved"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "ifc_model_path": {
                    "type": "string",
                    "required": True,
                    "description": "The IFC model the element is moved in.",
                },
                "element_global_id": {
                    "type": "string",
                    "required": True,
                    "description": "GlobalId of the element to move.",
                },
                "displacement": {
                    "type": "object",
                    "required": True,
                    "description": "The vector this run moves the element by.",
                },
            },
            "required": [
                "ifc_model_path",
                "element_global_id",
                "displacement",
            ],
        },
        output_schema={
            "type": "object",
            "properties": {
                "moved_position": {"type": "object"},
            },
            "required": ["moved_position"],
        },
        log_message={
            "info": {
                "en": "The element's own placement was moved.",
            },
            "debug_entry": {
                "en": "Adding the run's displacement to the element's placement.",
            },
        },
    )

    AXES: ClassVar[Tuple[str, str, str]] = ("x", "y", "z")
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    MOVED_POSITION_KEY: ClassVar[str] = "moved_position"

    def __init__(self, mover: Optional[IfcElementMoverPort] = None) -> None:
        self._mover: IfcElementMoverPort = mover or IfcElementMover()

    def label(self, lang: str = "en") -> str:
        return IfcElementMoveProcessState.ELEMENT_MOVED.label(lang)

    def description(self, lang: str = "en") -> str:
        return IfcElementMoveProcessState.ELEMENT_MOVED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ifc_model_path: str = RequiredParameter.of(
            context,
            IfcElementMoveContextKeys.IFC_MODEL_PATH_KEY,
        )
        global_id: str = RequiredParameter.of(
            context,
            IfcElementMoveContextKeys.ELEMENT_GLOBAL_ID_KEY,
        )
        displacement: Dict[str, float] = self._displacement(context)

        moved: Dict[str, Tuple[float, float, float]] = self._mover.displace(
            Path(ifc_model_path).expanduser().resolve(),
            global_id,
            displacement,
        )
        moved_position: Dict[str, List[float]] = {
            key: list(value) for key, value in moved.items()
        }
        context.set_parameter_value(
            IfcElementMoveContextKeys.MOVED_POSITION_KEY,
            moved_position,
        )

        return {
            self.RESULTING_STATE_KEY: IfcElementMoveProcessState.ELEMENT_MOVED,
            self.MOVED_POSITION_KEY: moved_position,
        }

    @classmethod
    def _displacement(cls, context: CliContextPort) -> Dict[str, float]:
        value: Any = context.get_parameter_value(
            IfcElementMoveContextKeys.DISPLACEMENT_KEY
        )
        if not isinstance(value, dict) or not all(
            axis in value and isinstance(value[axis], (int, float))
            and not isinstance(value[axis], bool)
            for axis in cls.AXES
        ):
            raise IfcCreationError(
                "No valid displacement vector is defined for this run."
            )

        return {axis: float(value[axis]) for axis in cls.AXES}
