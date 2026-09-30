from abc import ABC, abstractmethod
from pathlib import Path

from infobim.dict.domain.model.definition import DictionaryEntry


class DictionaryEntryFetcherPort(ABC):
    """
    Retrieves the document a dictionary URI names.
    """

    @abstractmethod
    def fetch(self, uri: str, destination: Path) -> Path:
        """
        Store what the URI returns at the destination and return it.
        """
        ...


class DictionaryDefinitionReaderPort(ABC):
    """
    Reads the definitions a retrieved dictionary document declares.
    """

    @abstractmethod
    def read(self, document_path: Path, source_uri: str) -> DictionaryEntry:
        """
        Return everything the document declares, or fail saying why not.
        """
        ...
