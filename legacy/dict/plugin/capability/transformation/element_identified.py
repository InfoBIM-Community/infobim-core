from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.product import IfcProductAssembler
from infobim.dict.plugin.machine.dictionary_entity_create.state import (
    DictionaryEntityContextKeys,
    DictionaryEntityCreateProcessState,
)


class ElementIdentifiedCapability(TransactionCapability):
    """
    Gives the element being defined the identity the project's rule gives it.

    An identity is not minted here and it is not asked of the caller.
    The project already has a rule for what the element of a given title
    is — derived from its own IfcProject and that title — and this uses
    that same rule, so an element defined from a dictionary and the
    element the IFC creation flow assembles under the same title are one
    element rather than two that happen to share a name.

    Deriving it is a state of its own because everything after it is
    filed under it: the dictionary entry this run downloads is stored
    under the identity of the element it defines, and an identity decided
    halfway through the download would be an identity decided by the
    download.

    The ``--global-id`` of this executable names the Project, never one of
    its elements, so what this binds is kept under a key of its own.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.dict.plugin.capability.transformation.target."
            "element_identified"
        ),
        version="0.1.0",
        name="Element Identified",
        description=(
            "Derive the identity of the element the dictionary entry defines."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "dict", "dictionary", "element_identified"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the element belongs to.",
                },
                "title": {
                    "type": "string",
                    "required": True,
                    "description": "Title of the element the entry defines.",
                },
            },
            "required": ["container_path", "title"],
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
                "en": "The element the dictionary entry defines is identified.",
            },
            "debug_entry": {
                "en": "Deriving the identity of the element being defined.",
            },
        },
    )

    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"

    def label(self, lang: str = "en") -> str:
        return DictionaryEntityCreateProcessState.ELEMENT_IDENTIFIED.label(lang)

    def description(self, lang: str = "en") -> str:
        return DictionaryEntityCreateProcessState.ELEMENT_IDENTIFIED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Bind the identity the element of this title carries.
        """
        container_path: Path = Path(
            self._stated(context, DictionaryEntityContextKeys.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        title: str = self._stated(context, DictionaryEntityContextKeys.TITLE_KEY)

        element_global_id: str = IfcProductAssembler.global_id_of(
            container_path,
            title,
        )
        context.set_parameter_value(
            DictionaryEntityContextKeys.ELEMENT_GLOBAL_ID_KEY,
            element_global_id,
        )

        return {
            self.RESULTING_STATE_KEY: (
                DictionaryEntityCreateProcessState.ELEMENT_IDENTIFIED
            ),
            DictionaryEntityContextKeys.ELEMENT_GLOBAL_ID_KEY: element_global_id,
        }

    @staticmethod
    def _stated(context: CliContextPort, key: str) -> str:
        """
        Return what the run states under a key, or fail saying it states none.
        """
        value: Any = context.get_parameter_value(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"The dictionary run states no '{key}', which this state "
                f"cannot be reached without."
            )

        return value.strip()
