from pathlib import Path
from typing import Optional

from infobim.project.domain.model.contract import IFC_PROJECT_CLASS_URI, PROJECT_DATASET_NAME
from ontobdc.context.adapter.dataset_instance import DatasetEntityInstanceRepository
from ontobdc.storage.plugin.check.is_dataset_facade_valid.check import main as check_facade


def evaluate(*, container_path: str) -> bool:
    dataset_path = Path(container_path).expanduser().resolve() / PROJECT_DATASET_NAME
    if not dataset_path.is_dir():
        return False
    if check_facade(dataset_path=str(dataset_path)) != 0:
        return False
    try:
        payload = DatasetEntityInstanceRepository(
            dataset_path=str(dataset_path),
            entity=IFC_PROJECT_CLASS_URI,
        ).list_instances()
    except Exception:
        return False
    return int(payload.get("instance_count") or 0) == 1


def main(container_path: Optional[str] = None) -> int:
    if not container_path:
        return 1
    return 0 if evaluate(container_path=container_path) else 1
