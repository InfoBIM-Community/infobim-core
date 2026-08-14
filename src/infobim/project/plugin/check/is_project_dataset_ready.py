from pathlib import Path
from typing import Optional

from infobim.project.domain.model.contract import PROJECT_DATASET_NAME
from ontobdc.storage.plugin.check.is_dataset_container_index_ready.check import main as check_container_index
from ontobdc.storage.plugin.check.is_dataset_metadata_ready.check import main as check_metadata


def project_dataset_path(container_path: str) -> Path:
    return Path(container_path).expanduser().resolve() / PROJECT_DATASET_NAME


def evaluate(*, container_path: str, root_path: str) -> bool:
    dataset_path = project_dataset_path(container_path)
    if not dataset_path.is_dir():
        return False
    return (
        check_metadata(root_path=root_path, dataset_path=str(dataset_path)) == 0
        and check_container_index(root_path=root_path, dataset_path=str(dataset_path)) == 0
    )


def main(container_path: Optional[str] = None, root_path: Optional[str] = None) -> int:
    if not container_path or not root_path:
        return 1
    return 0 if evaluate(container_path=container_path, root_path=root_path) else 1
