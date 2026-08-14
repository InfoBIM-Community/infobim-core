import json
import os
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import unquote

from ontobdc.storage.adapter.bootstrap import (
    ONTOBDC_DIRECTORY_NAME,
    get_container_crate_metadata_file_path,
)
from ontobdc.storage.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.storage.plugin.check.is_container_metadata_ready.hotfix import (
    main as hotfix_container_metadata_ready,
)
from ontobdc.storage.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)
from ontobdc.storage.plugin.check.is_container_storage_index_ready.hotfix import (
    main as hotfix_container_storage_index_ready,
)


_IGNORED_MARKER_DIR_NAMES: Set[str] = {ONTOBDC_DIRECTORY_NAME, ".__onmtobdc__"}
_DATASET_MARKER_FILE_NAMES: Set[str] = {"dataset.ttl", "nid.ttl"}
_DATASET_LINKSET_DIR_NAME: str = "linkset"
_DATASET_DATAPACKAGE_FILE_NAME: str = "datapackage.json"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _is_dataset_dir(candidate_dir: Path) -> bool:
    marker_dir: Path = candidate_dir / ONTOBDC_DIRECTORY_NAME
    if marker_dir.is_dir():
        for file_name in _DATASET_MARKER_FILE_NAMES:
            if (marker_dir / file_name).is_file():
                return True

    datapackage_file: Path = candidate_dir / _DATASET_LINKSET_DIR_NAME / _DATASET_DATAPACKAGE_FILE_NAME
    return datapackage_file.is_file()


def _iter_container_files(container_path: Path) -> List[str]:
    files: List[str] = []
    for root, dir_names, file_names in os.walk(container_path, topdown=True):
        root_path: Path = Path(root)
        dir_names[:] = [
            dir_name
            for dir_name in dir_names
            if dir_name not in _IGNORED_MARKER_DIR_NAMES
            and not _is_dataset_dir(root_path / dir_name)
        ]

        for file_name in file_names:
            file_path: Path = root_path / file_name
            relative_path: str = file_path.relative_to(container_path).as_posix()
            if relative_path.strip():
                files.append(relative_path)

    return sorted(set(files))


def _extract_has_part_ids(crate_data: dict) -> Optional[Set[str]]:
    graph_data: object = crate_data.get("@graph")
    if not isinstance(graph_data, list):
        return None

    dataset_node: Optional[dict] = None
    for node in graph_data:
        if isinstance(node, dict) and node.get("@id") == "./":
            dataset_node = node
            break

    if dataset_node is None:
        return None

    has_part: object = dataset_node.get("hasPart")
    if has_part is None:
        return set()
    if not isinstance(has_part, list):
        return None

    file_ids: Set[str] = set()
    for part in has_part:
        if not isinstance(part, dict):
            return None

        part_id: object = part.get("@id")
        if not isinstance(part_id, str) or not part_id.strip():
            return None

        normalized_id: str = part_id.strip()
        if normalized_id.startswith("./"):
            normalized_id = normalized_id[2:]
        file_ids.add(unquote(normalized_id))

    return file_ids


def check_project_container_updated(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_container_path: Optional[Path] = _resolve_path(container_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_container_path is None or resolved_root_path is None:
        return 1

    if check_container_metadata_ready(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    if check_container_storage_index_ready(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    crate_file: Path = get_container_crate_metadata_file_path(resolved_container_path)
    if not crate_file.is_file():
        return 1

    try:
        crate_data: object = json.loads(crate_file.read_text(encoding="utf-8"))
    except Exception:
        return 1

    if not isinstance(crate_data, dict):
        return 1

    expected_file_ids: Set[str] = set(_iter_container_files(resolved_container_path))
    crate_file_ids: Optional[Set[str]] = _extract_has_part_ids(crate_data)
    if crate_file_ids is None:
        return 1

    if crate_file_ids != expected_file_ids:
        return 1

    return 0


def hotfix_project_container_updated(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_container_path: Optional[Path] = _resolve_path(container_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_container_path is None or resolved_root_path is None:
        return 1

    if check_container_metadata_ready(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        if hotfix_container_metadata_ready(
            container_path=str(resolved_container_path),
            root_path=str(resolved_root_path),
        ) != 0:
            return 1

    if check_container_storage_index_ready(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        if hotfix_container_storage_index_ready(
            container_path=str(resolved_container_path),
            root_path=str(resolved_root_path),
        ) != 0:
            return 1

    if hotfix_container_manifest_synced(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    return check_project_container_updated(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    )
