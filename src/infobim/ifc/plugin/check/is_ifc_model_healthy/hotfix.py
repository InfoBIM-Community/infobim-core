"""Declare readable IFC models without converting their schema or rewriting them."""

import os
import json
from typing import Any, Dict, Optional, Set
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote, unquote

from ontobdc.storage.adapter.bootstrap import StorageBootstrap


_CRATE_ROOT_NODE_ID: str = "./"
_CRATE_GRAPH_KEY: str = "@graph"
_CRATE_NODE_ID_KEY: str = "@id"
_CRATE_TYPE_KEY: str = "@type"
_CRATE_HAS_PART_KEY: str = "hasPart"
_CRATE_FILE_TYPE: str = "File"
_CRATE_INDENT: int = 4


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _project_path(
    project_path: Optional[str],
    container_path: Optional[str],
) -> Optional[Path]:
    return _resolve_path(project_path) or _resolve_path(container_path)


def _crate_file_path(project_path: Path) -> Path:
    return StorageBootstrap.get_container_crate_metadata_file_path(project_path)


def _load_crate(project_path: Path) -> Optional[Dict[str, Any]]:
    crate_file: Path = _crate_file_path(project_path)
    if not crate_file.is_file():
        return None

    try:
        crate_data: Any = json.loads(crate_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(crate_data, dict):
        return None

    return crate_data


def _root_node(crate_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    graph_data: Any = crate_data.get(_CRATE_GRAPH_KEY)
    if not isinstance(graph_data, list):
        return None

    for node in graph_data:
        if isinstance(node, dict) and node.get(_CRATE_NODE_ID_KEY) == _CRATE_ROOT_NODE_ID:
            return node

    return None


def _crate_file_ids(project_path: Path) -> Optional[Set[str]]:
    crate_data: Optional[Dict[str, Any]] = _load_crate(project_path)
    if crate_data is None:
        return None

    root: Optional[Dict[str, Any]] = _root_node(crate_data)
    if root is None:
        return None

    parts: Any = root.get(_CRATE_HAS_PART_KEY)
    if parts is None:
        return set()
    if not isinstance(parts, list):
        return None

    file_ids: Set[str] = set()
    for part in parts:
        if not isinstance(part, dict):
            continue

        part_id: Any = part.get(_CRATE_NODE_ID_KEY)
        if not isinstance(part_id, str) or not part_id.strip():
            continue

        file_ids.add(unquote(part_id.strip()))

    return file_ids


def _is_declared(project_path: Path, model_path: Path) -> bool:
    if not model_path.is_relative_to(project_path):
        return False

    file_ids: Optional[Set[str]] = _crate_file_ids(project_path)
    if file_ids is None:
        return False

    return str(model_path.relative_to(project_path)) in file_ids


def _file_properties(file_path: Path) -> Optional[Dict[str, Any]]:
    try:
        stat_result = file_path.stat()
    except OSError:
        return None

    properties: Dict[str, Any] = {
        "name": file_path.name,
        "contentSize": str(stat_result.st_size),
        "dateModified": _iso_utc(stat_result.st_mtime),
    }

    birth_time: Optional[float] = getattr(stat_result, "st_birthtime", None)
    if birth_time is None and os.name == "nt":
        birth_time = stat_result.st_ctime
    if birth_time is not None:
        properties["dateCreated"] = _iso_utc(float(birth_time))

    return properties


def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _declare_model(project_path: Path, model_path: Path) -> bool:
    """Add ``model_path`` to the crate's ``hasPart``, changing nothing else.

    Called only for a model readable in its own schema and not yet declared
    in the project's manifest. The model itself is never rewritten.
    """
    crate_file: Path = _crate_file_path(project_path)
    crate_data: Optional[Dict[str, Any]] = _load_crate(project_path)
    if crate_data is None:
        return False

    root: Optional[Dict[str, Any]] = _root_node(crate_data)
    graph_data: Any = crate_data.get(_CRATE_GRAPH_KEY)
    if root is None or not isinstance(graph_data, list):
        return False

    properties: Optional[Dict[str, Any]] = _file_properties(model_path)
    if properties is None:
        return False

    relative_id: str = quote(str(model_path.relative_to(project_path)))

    file_node: Optional[Dict[str, Any]] = None
    node: Any
    for node in graph_data:
        if isinstance(node, dict) and node.get(_CRATE_NODE_ID_KEY) == relative_id:
            file_node = node
            break
    if file_node is None:
        file_node = {_CRATE_NODE_ID_KEY: relative_id, _CRATE_TYPE_KEY: _CRATE_FILE_TYPE}
        graph_data.append(file_node)
    else:
        file_node[_CRATE_TYPE_KEY] = _CRATE_FILE_TYPE
    file_node.update(properties)

    parts: Any = root.get(_CRATE_HAS_PART_KEY)
    if parts is None:
        parts = []
        root[_CRATE_HAS_PART_KEY] = parts
    if not isinstance(parts, list):
        return False
    if not any(
        isinstance(part, dict) and part.get(_CRATE_NODE_ID_KEY) == relative_id
        for part in parts
    ):
        parts.append({_CRATE_NODE_ID_KEY: relative_id})

    try:
        crate_file.write_text(
            json.dumps(crate_data, indent=_CRATE_INDENT, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        return False

    return True


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    resolved_project_path: Optional[Path] = _project_path(
        project_path,
        container_path,
    )
    resolved_model_path: Optional[Path] = _resolve_path(ifc_model_path)
    if resolved_project_path is None or resolved_model_path is None:
        return 1

    if not resolved_model_path.is_file():
        return 1

    if not os.access(resolved_model_path, os.W_OK):
        return 1

    # Imported here, not at module level: importing this module (as the
    # project refresh machine does) must not require ifcopenshell, which is
    # unavailable in some runtimes (e.g. Pyodide). Only checking a model does.
    import ifcopenshell

    try:
        ifcopenshell.open(str(resolved_model_path))
    except Exception:
        return 1

    if _is_declared(resolved_project_path, resolved_model_path):
        return 0

    if not _declare_model(resolved_project_path, resolved_model_path):
        return 1

    return 0 if _is_declared(resolved_project_path, resolved_model_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
