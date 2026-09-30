from typing import Any, ClassVar, Dict, Optional
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.dict.adapter.entry import DictionaryEntryFetcher
from infobim.dict.adapter.state import DictionaryEntityState
from infobim.dict.domain.port.dictionary import DictionaryEntryFetcherPort
from infobim.dict.plugin.machine.dictionary_entity_create.state import (
    DictionaryEntityContextKeys,
    DictionaryEntityCreateProcessState,
)


class DictionaryEntryDownloadedCapability(TransactionCapability):
    """
    Retrieves the dictionary entry this run defines an element from.

    What a dictionary says is not the project's to decide, so the entry is
    taken as it is served and stored unchanged, under the identity of the
    element it is going to define. Storing it is the point of the state:
    the dictionary lives somewhere else and may be edited, moved or taken
    down, and an element defined from a URL alone would be an element the
    project can no longer explain.

    Reaching the dictionary and reading it are kept apart on purpose. A
    network that did not answer and a document that does not say what it
    was expected to say are different failures with different remedies,
    and a state that did both would report either one as the other.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.dict.plugin.capability.transformation.target."
            "dictionary_entry_downloaded"
        ),
        version="0.1.0",
        name="Dictionary Entry Downloaded",
        description=(
            "Retrieve the dictionary entry the --kind resolver located and "
            "store it in the project's own state."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "dict", "dictionary", "dictionary_entry_downloaded"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the element belongs to.",
                },
                "element_global_id": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "The IFC GlobalId of the element the entry defines."
                    ),
                },
                "dictionary_uri": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "Filesystem path of the dictionary entry document, as "
                        "resolved by KindStrategy from the --kind flag."
                    ),
                },
                "kind": {
                    "type": "string",
                    "required": False,
                    "description": (
                        "Original --kind value supplied by the caller, kept "
                        "for traceability alongside the resolved entry."
                    ),
                },
                "aeco_class_uri": {
                    "type": "string",
                    "required": False,
                    "description": (
                        "AECO class URI matched in kind.ttl from which the "
                        "dictionary entry was reverse-located."
                    ),
                },
            },
            "required": ["container_path", "element_global_id", "dictionary_uri"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "dictionary_entry_path": {"type": "string"},
            },
            "required": ["dictionary_entry_path"],
        },
        log_message={
            "info": {
                "en": "The dictionary entry was downloaded into the project.",
            },
            "debug_entry": {
                "en": "Downloading the dictionary entry the --kind resolver located.",
            },
        },
    )

    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"

    def __init__(
        self,
        fetcher: Optional[DictionaryEntryFetcherPort] = None,
    ) -> None:
        self._fetcher: DictionaryEntryFetcherPort = fetcher or DictionaryEntryFetcher()

    def label(self, lang: str = "en") -> str:
        return DictionaryEntityCreateProcessState.DICTIONARY_ENTRY_DOWNLOADED.label(
            lang
        )

    def description(self, lang: str = "en") -> str:
        return (
            DictionaryEntityCreateProcessState.DICTIONARY_ENTRY_DOWNLOADED.description(
                lang
            )
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Store what the dictionary answers, under the element's identity.
        """
        container_path: Path = Path(
            self._stated(context, DictionaryEntityContextKeys.CONTAINER_PATH_KEY)
        ).expanduser().resolve()
        element_global_id: str = self._stated(
            context,
            DictionaryEntityContextKeys.ELEMENT_GLOBAL_ID_KEY,
        )
        dictionary_uri: str = self._stated(
            context,
            DictionaryEntityContextKeys.DICTIONARY_URI_KEY,
        )

        entry_path: Path = self._fetcher.fetch(
            dictionary_uri,
            DictionaryEntityState.path_of(
                container_path,
                element_global_id,
                DictionaryEntityState.ENTRY_FILE_NAME,
            ),
        )
        context.set_parameter_value(
            DictionaryEntityContextKeys.DICTIONARY_ENTRY_PATH_KEY,
            str(entry_path),
        )

        return {
            self.RESULTING_STATE_KEY: (
                DictionaryEntityCreateProcessState.DICTIONARY_ENTRY_DOWNLOADED
            ),
            DictionaryEntityContextKeys.DICTIONARY_ENTRY_PATH_KEY: str(entry_path),
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
