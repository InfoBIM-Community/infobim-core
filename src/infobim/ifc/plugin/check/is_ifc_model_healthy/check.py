"""Check declaration, writability and readability in the model's own IFC schema."""

import os
import json
from typing import List, Optional, Set
from pathlib import Path
from urllib.parse import unquote

from ontobdc.storage.adapter.bootstrap import StorageBootstrap


_CRATE_ROOT_NODE_ID: str = "./"
_CRATE_GRAPH_KEY: str = "@graph"
_CRATE_NODE_ID_KEY: str = "@id"
_CRATE_HAS_PART_KEY: str = "hasPart"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _project_path(
    project_path: Optional[str],
    container_path: Optional[str],
) -> Optional[Path]:
    return _resolve_path(project_path) or _resolve_path(container_path)


def _crate_file_ids(project_path: Path) -> Optional[Set[str]]:
    crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(
        project_path,
    )
    if not crate_file.is_file():
        return None

    try:
        crate_data: object = json.loads(crate_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(crate_data, dict):
        return None

    graph_data: object = crate_data.get(_CRATE_GRAPH_KEY)
    if not isinstance(graph_data, list):
        return None

    for node in graph_data:
        if not isinstance(node, dict):
            continue
        if node.get(_CRATE_NODE_ID_KEY) != _CRATE_ROOT_NODE_ID:
            continue

        parts: object = node.get(_CRATE_HAS_PART_KEY)
        if parts is None:
            return set()
        if not isinstance(parts, list):
            return None

        file_ids: Set[str] = set()
        for part in parts:
            if not isinstance(part, dict):
                continue

            part_id: object = part.get(_CRATE_NODE_ID_KEY)
            if not isinstance(part_id, str) or not part_id.strip():
                continue

            file_ids.add(_crate_path(part_id))

        return file_ids

    return None


def _crate_path(node_id: str) -> str:
    file_path: str = unquote(node_id.strip())
    if file_path.startswith(_CRATE_ROOT_NODE_ID):
        return file_path[len(_CRATE_ROOT_NODE_ID):]

    return file_path


def _is_declared(project_path: Path, model_path: Path) -> bool:
    if not model_path.is_relative_to(project_path):
        return False

    file_ids: Optional[Set[str]] = _crate_file_ids(project_path)
    if file_ids is None:
        return False

    return str(model_path.relative_to(project_path)) in file_ids


def diagnose(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> List[str]:
    """
    Why the model is not healthy: one sentence per failed condition that could
    be told apart, none when it is healthy. Stops at the first failure that
    makes the next conditions meaningless.
    """
    resolved_project_path: Optional[Path] = _project_path(
        project_path,
        container_path,
    )
    resolved_model_path: Optional[Path] = _resolve_path(ifc_model_path)
    if resolved_project_path is None or resolved_model_path is None:
        return ["The project or the IFC model was not given."]

    if not resolved_model_path.is_file():
        return [f"The IFC file {resolved_model_path.name} does not exist."]

    findings: List[str] = []
    if not _is_declared(resolved_project_path, resolved_model_path):
        findings.append("The project's RO-Crate does not declare this model.")

    if not os.access(resolved_model_path, os.W_OK):
        findings.append("The IFC file is not writable.")

    # Imported here, not at module level: importing this module (as the
    # project refresh machine does) must not require ifcopenshell, which is
    # unavailable in some runtimes (e.g. Pyodide). Only checking a model does.
    import ifcopenshell

    try:
        ifcopenshell.open(str(resolved_model_path))
    except Exception as error:
        findings.append(f"The file does not read as an IFC STEP model: {error}")

    return findings


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    return 1 if diagnose(project_path, ifc_model_path, container_path) else 0


if __name__ == "__main__":
    raise SystemExit(main())
