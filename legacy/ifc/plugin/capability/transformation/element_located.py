from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.product import IfcProductAssembler
from infobim.ifc.domain.exception.creation import IfcElementNotFoundError
from infobim.ifc.plugin.machine.ifc_element_move.state import (
    IfcElementMoveContextKeys,
    IfcElementMoveProcessState,
)


class ElementLocatedCapability(TransactionCapability):
    """
    Gives the move the identity of the element it displaces, confirmed.

    The identity is derived the way every element of this project is
    identified — from the Project and the title, by the rule
    ``IfcProductAssembler`` itself derives a product's GlobalId by — so
    the element a title names here is the same element that title names
    everywhere else in this stack.

    A title deterministically names an identity whether or not anything
    was ever created under it, so the identity alone is not proof there
    is an element to move. This confirms it against the target model,
    because a run that moved nothing and reported success would be
    indistinguishable from one that moved the element the caller meant.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "element_located"
        ),
        version="0.1.0",
        name="Element Located",
        description=(
            "Derive the identity of the element this run moves, and confirm "
            "the target model carries it."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "element_located"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the element belongs to.",
                },
                "ifc_model_path": {
                    "type": "string",
                    "required": True,
                    "description": "The IFC model the element is moved in.",
                },
                "title": {
                    "type": "string",
                    "required": True,
                    "description": "Title of the element to move.",
                },
            },
            "required": ["container_path", "ifc_model_path", "title"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "element_global_id": {"type": "string"},
            },
            "required": ["element_global_id"],
        },
        log_message={
            "info": {
                "en": "The element this run moves is located.",
            },
            "debug_entry": {
                "en": "Deriving and confirming the identity of the element to move.",
            },
        },
    )

    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    ELEMENT_GLOBAL_ID_KEY: ClassVar[str] = "element_global_id"

    def label(self, lang: str = "en") -> str:
        return IfcElementMoveProcessState.ELEMENT_LOCATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return IfcElementMoveProcessState.ELEMENT_LOCATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        import ifcopenshell

        container_path: str = RequiredParameter.of(
            context,
            IfcElementMoveContextKeys.CONTAINER_PATH_KEY,
        )
        ifc_model_path: str = RequiredParameter.of(
            context,
            IfcElementMoveContextKeys.IFC_MODEL_PATH_KEY,
        )
        title: str = RequiredParameter.of(
            context,
            IfcElementMoveContextKeys.TITLE_KEY,
        )

        global_id: str = IfcProductAssembler.global_id_of(
            self._path(container_path),
            title,
        )

        model: Any = ifcopenshell.open(ifc_model_path)
        try:
            model.by_guid(global_id)
        except Exception as error:
            raise IfcElementNotFoundError(
                f"No element titled '{title}' was found in {ifc_model_path}. "
                f"Nothing was created under that title in this project's "
                f"target model."
            ) from error

        context.set_parameter_value(
            IfcElementMoveContextKeys.ELEMENT_GLOBAL_ID_KEY,
            global_id,
        )

        return {
            self.RESULTING_STATE_KEY: IfcElementMoveProcessState.ELEMENT_LOCATED,
            self.ELEMENT_GLOBAL_ID_KEY: global_id,
        }

    @staticmethod
    def _path(value: str) -> Path:
        return Path(value).expanduser().resolve()
