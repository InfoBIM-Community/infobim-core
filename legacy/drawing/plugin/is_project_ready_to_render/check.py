from pathlib import Path
from typing import List, Optional

from infobim.project.domain.model.contract import ProjectContract
from infobim.project.plugin.check.is_drawing_linked_to_project.check import (
    main as check_drawing_linked_to_project,
)


_LINKSET_DIRECTORY_NAME: str = "linkset"
_LINKSET_FILE_SUFFIX: str = ".ttl"


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

    linkset_paths: Optional[List[Path]] = _linkset_paths(resolved_project_path)
    if linkset_paths is None:
        return 1

    for linkset_path in linkset_paths:
        sub_result: int = check_drawing_linked_to_project(
            linkset_path=str(linkset_path)
        )
        if sub_result == 2:
            continue
        if sub_result != 0:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
