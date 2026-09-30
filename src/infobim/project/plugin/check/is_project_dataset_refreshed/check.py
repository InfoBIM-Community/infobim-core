from pathlib import Path
from typing import Optional

from infobim.project.domain.model.contract import ProjectContract
from ontobdc.container.plugin.check.is_dataset_metadata_ready.check import (
    main as check_dataset_metadata_ready,
)
from ontobdc.container.plugin.check.is_dataset_container_index_ready.check import (
    main as check_dataset_container_index_ready,
)


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def main(
    project_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_project_path: Optional[Path] = _resolve_path(project_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_project_path is None or resolved_root_path is None:
        return 1

    dataset_path: Path = resolved_project_path / ProjectContract.DATASET_NAME
    if not dataset_path.is_dir():
        return 1

    if check_dataset_metadata_ready(
        dataset_path=str(dataset_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    if check_dataset_container_index_ready(
        dataset_path=str(dataset_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
