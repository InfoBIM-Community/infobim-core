import json
from pathlib import Path
from typing import Any, ClassVar, List, Optional, Set
from urllib.parse import unquote

from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class IfcProjectModels:
    """
    The IFC models a project holds, as its RO-Crate declares them.
    """

    CRATE_ROOT_NODE_ID: ClassVar[str] = "./"
    CRATE_GRAPH_KEY: ClassVar[str] = "@graph"
    CRATE_NODE_ID_KEY: ClassVar[str] = "@id"
    CRATE_HAS_PART_KEY: ClassVar[str] = "hasPart"
    IFC_FILE_SUFFIXES: ClassVar[Set[str]] = {".ifc", ".ifczip", ".ifcxml"}

    @classmethod
    def paths(cls, project_path: Path) -> Optional[List[Path]]:
        """
        The IFC models the project's RO-Crate declares and that exist on
        disk, or None when the crate cannot be read.
        """
        file_ids: Optional[Set[str]] = cls._crate_file_ids(project_path)
        if file_ids is None:
            return None

        model_paths: List[Path] = []
        for file_id in file_ids:
            relative: Path = Path(file_id)
            if relative.is_absolute():
                continue
            if relative.suffix.lower() not in cls.IFC_FILE_SUFFIXES:
                continue
            absolute: Path = (project_path / relative).resolve()
            if absolute.is_file():
                model_paths.append(absolute)

        return model_paths

    @classmethod
    def _crate_file_ids(cls, project_path: Path) -> Optional[Set[str]]:
        crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(
            project_path,
        )
        if not crate_file.is_file():
            return None

        try:
            crate_data: Any = json.loads(crate_file.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not isinstance(crate_data, dict):
            return None

        graph_data: Any = crate_data.get(cls.CRATE_GRAPH_KEY)
        if not isinstance(graph_data, list):
            return None

        for node in graph_data:
            if not isinstance(node, dict):
                continue
            if node.get(cls.CRATE_NODE_ID_KEY) != cls.CRATE_ROOT_NODE_ID:
                continue

            parts: object = node.get(cls.CRATE_HAS_PART_KEY)
            if parts is None:
                return set()
            if not isinstance(parts, list):
                return None

            file_ids: Set[str] = set()
            for part in parts:
                if not isinstance(part, dict):
                    continue

                part_id: object = part.get(cls.CRATE_NODE_ID_KEY)
                if not isinstance(part_id, str) or not part_id.strip():
                    continue

                file_ids.add(cls._crate_path(part_id))

            return file_ids

        return None

    @classmethod
    def _crate_path(cls, node_id: str) -> str:
        file_path: str = unquote(node_id.strip())
        if file_path.startswith(cls.CRATE_ROOT_NODE_ID):
            return file_path[len(cls.CRATE_ROOT_NODE_ID):]

        return file_path
