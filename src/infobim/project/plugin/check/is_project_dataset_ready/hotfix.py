from pathlib import Path
from typing import Optional

from infobim.project.domain.model.contract import ProjectContract
from ontobdc.container.adapter.dataset import DatasetTitleRepository
from ontobdc.container.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata,
)
from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
    main as hotfix_container_metadata,
)
from ontobdc.container.plugin.check.is_dataset_metadata_ready.hotfix import (
    main as create_dataset_metadata,
)
from ontobdc.container.plugin.check.is_dataset_container_index_ready.hotfix import (
    main as index_dataset_in_container,
)
from infobim.project.plugin.check.is_project_dataset_ready.check import (
    main as check_project_dataset_ready,
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

    if not resolved_project_path.is_dir():
        return 1

    # The dataset is indexed in the container's metadata, which must first
    # describe the container where it is now (it may have been moved or
    # renamed since it was written).
    if check_container_metadata(
        container_path=str(resolved_project_path),
        root_path=str(resolved_root_path),
    ) != 0 and hotfix_container_metadata(
        container_path=str(resolved_project_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    dataset_path: Path = resolved_project_path / ProjectContract.DATASET_NAME
    if create_dataset_metadata(
        dataset_path=str(dataset_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    DatasetTitleRepository(dataset_path).write_title(ProjectContract.DATASET_TITLE)

    if index_dataset_in_container(
        dataset_path=str(dataset_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    return check_project_dataset_ready(
        project_path=str(resolved_project_path),
        root_path=str(resolved_root_path),
    )


if __name__ == "__main__":
    raise SystemExit(main())
