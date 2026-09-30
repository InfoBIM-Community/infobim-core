from typing import ClassVar
from pathlib import Path

from ontobdc.shared.adapter.etl import EtlDirectoryContract
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from infobim.dict.domain.exception.dictionary import DictionaryTargetInvalidError


class DictionaryEntityState:
    """
    Holds what a dictionary run downloaded, per element it defines.

    A dictionary entry is retrieved from somewhere outside the project,
    and what was retrieved is what the element was defined from. Keeping
    only the URI would leave the project unable to say what it read: the
    dictionary may be edited, moved or taken down, and an element defined
    last week would then be an element nobody can explain. So the document
    is stored beside the run, in the same persisted-state layout every
    other flow of this codebase uses,
    ``.__ontobdc__/etl/<module>/<phase>/<entity>/<element>/``.

    The element of that layout is the GlobalId, never a title. A title is
    what an element is called and an identity is what it is: two elements
    may be renamed into each other's titles, and the state of one is
    still not the state of the other. The identity is derived before
    anything is written here, so the state is filed under it from the
    first write and nothing has to be renamed afterwards.

    Defining the same element again replaces its document rather than
    adding another beside it: what defines an element is the entry this
    run read, and two entries under one identity would leave nothing able
    to say which of them the element was defined from.
    """

    ETL_MODULE_NAME: ClassVar[str] = "dict"
    ETL_PHASE_NAME: ClassVar[str] = "dictionary_entity_create"
    ETL_ENTITY_NAME: ClassVar[str] = "entity"
    ENTRY_FILE_NAME: ClassVar[str] = "__dictionary_entry__.ttl"

    @classmethod
    def path_of(cls, container_path: Path, global_id: str, file_name: str) -> Path:
        """
        Return one state file of the element the GlobalId names.
        """
        return cls.directory_of(container_path, global_id) / file_name

    @classmethod
    def directory_of(cls, container_path: Path, global_id: str) -> Path:
        """
        Return the directory the element's dictionary state lives in.
        """
        identity: str = global_id.strip()
        if not identity:
            raise DictionaryTargetInvalidError(
                "An element with no GlobalId cannot have dictionary state "
                "filed under one."
            )

        return cls.root_of(container_path) / identity

    @classmethod
    def root_of(cls, container_path: Path) -> Path:
        """
        Return where the project keeps what it read from dictionaries.
        """
        return StorageBootstrap.get_ontobdc_directory(container_path).joinpath(
            EtlDirectoryContract.DIRECTORY_NAME,
            cls.ETL_MODULE_NAME,
            cls.ETL_PHASE_NAME,
            cls.ETL_ENTITY_NAME,
        )
