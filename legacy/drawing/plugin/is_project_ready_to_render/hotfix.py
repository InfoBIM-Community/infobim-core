from pathlib import Path
from typing import List, Optional

from infobim.project.domain.model.contract import ProjectContract
from infobim.drawing.adapter.dxf_ifcx_linkset import DxfIfcxLinksetWriter
from infobim.drawing.adapter.transformation_payload import (
    TransformationPayloadPath,
)
from infobim.project.plugin.check.is_drawing_linked_to_project.check import (
    main as check_drawing_linked_to_project,
)
from infobim.project.plugin.check.is_drawing_linked_to_project.hotfix import (
    main as hotfix_drawing_linked_to_project,
)

from infobim.project.plugin.check.is_project_ready_to_render.check import (
    main as check_project_ready_to_render,
)


_LINKSET_DIRECTORY_NAME: str = "linkset"
_LINKSET_FILE_SUFFIX: str = ".ttl"
_IFCX_SUFFIX: str = ".ifcx"
_DXF_SUFFIX: str = ".dxf"
_DXF_IFCX_CACHE_SOURCE: str = "dwg"
_DXF_IFCX_CACHE_INTERMEDIATE: str = "dxf"
_DXF_IFCX_CACHE_TARGET: str = "ifcx"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _project_path(
    project_path: Optional[str],
    container_path: Optional[str],
) -> Optional[Path]:
    return _resolve_path(project_path) or _resolve_path(container_path)


def _linkset_directory(project_path: Path) -> Path:
    return (
        project_path
        / ProjectContract.DATASET_NAME
        / ProjectContract.PAYLOAD_DIRECTORY_NAME
        / _LINKSET_DIRECTORY_NAME
    )


def _linkset_paths(project_path: Path) -> Optional[List[Path]]:
    linkset_directory: Path = _linkset_directory(project_path)
    if not linkset_directory.is_dir():
        return []

    linkset_paths: List[Path] = []
    candidate: Path
    for candidate in linkset_directory.rglob(f"*{_LINKSET_FILE_SUFFIX}"):
        if candidate.is_file():
            linkset_paths.append(candidate.resolve())

    return linkset_paths


def _ifcx_paths(project_path: Path) -> List[Path]:
    ifcx_directory: Path = TransformationPayloadPath.directory_for(
        project_path,
        _DXF_IFCX_CACHE_INTERMEDIATE,
        _DXF_IFCX_CACHE_TARGET,
    )
    if not ifcx_directory.is_dir():
        return []

    ifcx_paths: List[Path] = []
    candidate: Path
    for candidate in ifcx_directory.rglob(f"*{_IFCX_SUFFIX}"):
        if candidate.is_file():
            ifcx_paths.append(candidate.resolve())
    return ifcx_paths


def _dxf_path_for_hash(project_path: Path, dxf_hash: str) -> Optional[Path]:
    dxf_cache: Path = TransformationPayloadPath.directory_for(
        project_path,
        _DXF_IFCX_CACHE_SOURCE,
        _DXF_IFCX_CACHE_INTERMEDIATE,
    )
    candidate: Path
    for candidate in dxf_cache.rglob(f"*{_DXF_SUFFIX}"):
        if not candidate.is_file():
            continue
        if TransformationPayloadPath.identifier_for(candidate) == dxf_hash:
            return candidate.resolve()
    return None


def _ensure_ifcx_linksets_exist(project_path: Path) -> int:
    ifcx_path: Path
    for ifcx_path in _ifcx_paths(project_path):
        dxf_hash: str = ifcx_path.stem
        dxf_path: Optional[Path] = _dxf_path_for_hash(project_path, dxf_hash)
        if dxf_path is None:
            continue
        try:
            DxfIfcxLinksetWriter.write(project_path, dxf_path, ifcx_path)
        except (OSError, ValueError):
            return 1
    return 0


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

    if _ensure_ifcx_linksets_exist(resolved_project_path) != 0:
        return 1

    linkset_paths: Optional[List[Path]] = _linkset_paths(resolved_project_path)
    if linkset_paths is None:
        return 1

    project_path_str: str = str(resolved_project_path)
    for linkset_path in linkset_paths:
        sub_check_result: int = check_drawing_linked_to_project(
            linkset_path=str(linkset_path)
        )
        if sub_check_result == 2:
            continue
        if hotfix_drawing_linked_to_project(
            linkset_path=str(linkset_path),
            container_path=project_path_str,
        ) != 0:
            return 1

    return check_project_ready_to_render(
        project_path=project_path_str,
        container_path=project_path_str,
    )


if __name__ == "__main__":
    raise SystemExit(main())
