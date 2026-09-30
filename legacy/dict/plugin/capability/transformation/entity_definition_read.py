from typing import Any, ClassVar, Dict, List, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.dict.adapter.definition import DictionaryDefinitionReader
from infobim.dict.domain.model.definition import DictionaryEntry
from infobim.dict.domain.port.dictionary import DictionaryDefinitionReaderPort
from infobim.dict.plugin.machine.dictionary_entity_create.state import (
    DictionaryEntityContextKeys,
    DictionaryEntityCreateProcessState,
)


class EntityDefinitionReadCapability(TransactionCapability):
    """
    Reads what the downloaded entry declares about the element.

    The entry is read from the copy the previous state stored, never from
    the dictionary again: what was downloaded is what this element is
    defined from, and fetching it twice would leave the run unable to say
    which of the two answers it understood.

    What comes out of this is the definition itself — the IFC class, the
    predefined type it is restricted to, the classes the element also
    belongs to, the shape it is described by — bound to this run as an
    object the context keeps in memory. Nothing is written into the
    project's model here: a definition read is a definition understood,
    and the states after this one are the ones that build it.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.dict.plugin.capability.transformation.target."
            "entity_definition_read"
        ),
        version="0.1.0",
        name="Entity Definition Read",
        description=(
            "Read the definitions the downloaded dictionary entry declares "
            "for the element."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "dict", "dictionary", "entity_definition_read"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "dictionary_entry_path": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "The dictionary entry this run stored in the project."
                    ),
                },
                "dictionary_uri": {
                    "type": "string",
                    "required": True,
                    "description": "The dictionary the entry was read from.",
                },
            },
            "required": ["dictionary_entry_path", "dictionary_uri"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "definitions": {"type": "array"},
            },
            "required": ["definitions"],
        },
        log_message={
            "info": {
                "en": "The definitions the dictionary entry declares were read.",
            },
            "debug_entry": {
                "en": "Reading the definitions the dictionary entry declares.",
            },
        },
    )

    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    DEFINITIONS_KEY: ClassVar[str] = "definitions"

    def __init__(
        self,
        reader: Optional[DictionaryDefinitionReaderPort] = None,
    ) -> None:
        self._reader: DictionaryDefinitionReaderPort = (
            reader or DictionaryDefinitionReader()
        )

    def label(self, lang: str = "en") -> str:
        return DictionaryEntityCreateProcessState.ENTITY_DEFINITION_READ.label(lang)

    def description(self, lang: str = "en") -> str:
        return DictionaryEntityCreateProcessState.ENTITY_DEFINITION_READ.description(
            lang
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Bind what the entry declares, for this run to define the element by.
        """
        entry_path: Path = Path(
            self._stated(
                context,
                DictionaryEntityContextKeys.DICTIONARY_ENTRY_PATH_KEY,
            )
        )
        dictionary_uri: str = self._stated(
            context,
            DictionaryEntityContextKeys.DICTIONARY_URI_KEY,
        )

        entry: DictionaryEntry = self._reader.read(entry_path, dictionary_uri)
        context.set_parameter_value(
            DictionaryEntityContextKeys.DICTIONARY_DEFINITION_KEY,
            entry,
        )
        definitions: List[Dict[str, Any]] = [
            definition.to_dict() for definition in entry.definitions
        ]

        return {
            self.RESULTING_STATE_KEY: (
                DictionaryEntityCreateProcessState.ENTITY_DEFINITION_READ
            ),
            self.DEFINITIONS_KEY: definitions,
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
