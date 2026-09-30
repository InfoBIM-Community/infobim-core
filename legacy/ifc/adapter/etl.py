import json
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional

from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from infobim.ifc.domain.port.composition import IfcConversionStatePort


class IfcConversionState(IfcConversionStatePort):
    """
    What the project records about converting one IFC element to IFCX.

    The record is provenance and it is per element: it says which schema the
    element was read under, which capabilities produced its IFCX, and which
    nodes that IFCX contributed to the project's canonical model. Converting
    the same element again reads its own record, replaces the nodes it names
    and writes the record back, so a rerun updates that element instead of
    leaving a second, unrelated conversion behind.

    It is a record, not a gate: nothing here turns a rerun into a no-op.
    """

    ETL_DIRECTORY_NAME: ClassVar[str] = "etl"
    ETL_MODULE_NAME: ClassVar[str] = "ifc"
    ETL_PHASE_NAME: ClassVar[str] = "conversion"
    ETL_ENTITY_NAME: ClassVar[str] = "element"
    ETL_EVENT_FILE_NAME: ClassVar[str] = "__ifc_to_ifcx__.json"

    NODES_KEY: ClassVar[str] = "nodes"

    def read(self, project_path: Path, element_id: str) -> Optional[Dict[str, Any]]:
        record_path: Path = self._record_path(project_path, element_id)
        if not record_path.is_file():
            return None

        recorded: Any = json.loads(record_path.read_text(encoding="utf-8"))
        if not isinstance(recorded, dict):
            raise ValueError(
                f"The conversion record of {element_id} must be an object: "
                f"{record_path}."
            )

        return recorded

    def write(
        self,
        project_path: Path,
        element_id: str,
        state: Dict[str, Any],
    ) -> Path:
        record_path: Path = self._record_path(project_path, element_id)
        record_path.parent.mkdir(parents=True, exist_ok=True)
        serialized: str = json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        temporary_path: Path = record_path.with_name(f".{record_path.name}.tmp")
        temporary_path.write_text(serialized + "\n", encoding="utf-8")
        temporary_path.replace(record_path)

        return record_path

    @classmethod
    def _record_path(cls, project_path: Path, element_id: str) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(project_path)
            / cls.ETL_DIRECTORY_NAME
            / cls.ETL_MODULE_NAME
            / cls.ETL_PHASE_NAME
            / cls.ETL_ENTITY_NAME
            / element_id
            / cls.ETL_EVENT_FILE_NAME
        )
