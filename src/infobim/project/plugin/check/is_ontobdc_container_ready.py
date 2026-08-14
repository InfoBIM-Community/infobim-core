from pathlib import Path
from typing import Optional

from ontobdc.storage.plugin.check.is_container_manifest_synced.check import main as check_manifest
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import main as check_metadata
from ontobdc.storage.plugin.check.is_container_storage_index_ready.check import main as check_storage_index


def evaluate(*, container_path: str, root_path: str) -> bool:
    target = Path(container_path).expanduser().resolve()
    if not target.is_dir():
        return False
    return (
        check_metadata(root_path=root_path, container_path=str(target)) == 0
        and check_storage_index(root_path=root_path, container_path=str(target)) == 0
        and check_manifest(root_path=root_path, container_path=str(target)) == 0
    )


def main(container_path: Optional[str] = None, root_path: Optional[str] = None) -> int:
    if not container_path or not root_path:
        return 1
    return 0 if evaluate(container_path=container_path, root_path=root_path) else 1
