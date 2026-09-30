from pathlib import Path

from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ExecutionContainer:
    @staticmethod
    def locate(directory: Path) -> Path:
        candidate: Path
        for candidate in (directory.resolve(), *directory.resolve().parents):
            if StorageBootstrap.get_container_storage_file_path(candidate).is_file():
                return candidate
        raise ValueError(f"No container metadata was found for execution directory {directory}.")
