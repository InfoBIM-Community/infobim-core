import json
from pathlib import Path
from typing import Any, Callable, List, Optional, Set
from urllib.parse import unquote

from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from infobim.project.domain.model.contract import ProjectContract

from infobim.ifc.plugin.check.is_geometric_representation_context_ready.hotfix import (
    main as hotfix_geometric_representation_context_ready,
)
from infobim.ifc.plugin.check.is_ifc_model_healthy.hotfix import (
    main as hotfix_ifc_model_healthy,
)
from infobim.ifc.plugin.check.is_shape_representation_context_valid.hotfix import (
    main as hotfix_shape_representation_context_valid,
)
from infobim.ifc.plugin.check.is_spatial_structure_valid.hotfix import (
    main as hotfix_spatial_structure_valid,
)
from infobim.ifc.plugin.check.is_unit_defined.hotfix import (
    main as hotfix_unit_defined,
)

from infobim.project.plugin.check.is_ifc_models_refreshed.check import (
    main as check_ifc_models_refreshed,
)


_CRATE_ROOT_NODE_ID: str = "./"
_CRATE_GRAPH_KEY: str = "@graph"
_CRATE_NODE_ID_KEY: str = "@id"
_CRATE_HAS_PART_KEY: str = "hasPart"

_IFC_FILE_SUFFIXES: Set[str] = {".ifc", ".ifczip", ".ifcxml"}

_PER_MODEL_HOTFIXES: List[Callable[..., int]] = [
    hotfix_ifc_model_healthy,
    hotfix_unit_defined,
    hotfix_geometric_representation_context_ready,
    hotfix_shape_representation_context_valid,
    hotfix_spatial_structure_valid,
]


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
        crate_data: Any = json.loads(crate_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(crate_data, dict):
        return None

    graph_data: Any = crate_data.get(_CRATE_GRAPH_KEY)
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


def _ifc_model_paths(project_path: Path) -> Optional[List[Path]]:
    file_ids: Optional[Set[str]] = _crate_file_ids(project_path)
    if file_ids is None:
        return None

    model_paths: List[Path] = []
    for file_id in file_ids:
        relative: Path = Path(file_id)
        if relative.is_absolute():
            continue
        if relative.suffix.lower() not in _IFC_FILE_SUFFIXES:
            continue
        absolute: Path = (project_path / relative).resolve()
        if absolute.is_file():
            model_paths.append(absolute)

    return model_paths


def _apply_per_model_hotfixes(project_path_str: str, model_path_str: str) -> bool:
    for hotfix_fn in _PER_MODEL_HOTFIXES:
        if hotfix_fn(
            project_path=project_path_str,
            ifc_model_path=model_path_str,
            container_path=project_path_str,
        ) != 0:
            return False

    return True


def main(
    project_path: Optional[str] = None,
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    del root_path

    resolved_project_path: Optional[Path] = _project_path(
        project_path,
        container_path,
    )
    if resolved_project_path is None:
        return 1

    model_paths: Optional[List[Path]] = _ifc_model_paths(resolved_project_path)
    if model_paths is None:
        return 1

    project_path_str: str = str(resolved_project_path)
    for model_path in model_paths:
        if not _apply_per_model_hotfixes(project_path_str, str(model_path)):
            return 1

    return check_ifc_models_refreshed(
        project_path=project_path_str,
        container_path=project_path_str,
    )


if __name__ == "__main__":
    raise SystemExit(main())
