import hashlib
from pathlib import Path
from typing import Any, List

from ontobdc.context.adapter.repository import LocalContextFileResource


class ElementImportStepRepository:
    FILE_TYPES: List[str] = ["yaml", "yml", "jsonld", "json", "ttl", "md", "txt", "rdf", "xml"]

    def __init__(
        self,
        container_path: str,
        source_path: str,
        element_name: str,
    ) -> None:
        self._container_path: Path = Path(container_path).expanduser().resolve()
        self._source_path: Path = Path(source_path).expanduser().resolve()
        self._element_name: str = str(element_name).strip()

        if not self._container_path.exists() or not self._container_path.is_dir():
            raise FileNotFoundError(f"Project container not found: {self._container_path}")
        if not self._source_path.exists() or not self._source_path.is_file():
            raise FileNotFoundError(f"Import source not found: {self._source_path}")
        if not self._element_name:
            raise ValueError("Element name is required for the project import step repository.")

        self._source_hash: str = hashlib.sha256(self._source_path.read_bytes()).hexdigest()
        self._step_dir: Path = (
            self._container_path
            / ".__ontobdc__"
            / "etl"
            / "element"
            / self._element_name
            / self._source_hash
        )
        self._step_dir.mkdir(parents=True, exist_ok=True)

    @property
    def source_path(self) -> Path:
        return self._source_path

    @property
    def element_name(self) -> str:
        return self._element_name

    @property
    def source_hash(self) -> str:
        return self._source_hash

    @property
    def step_dir(self) -> Path:
        return self._step_dir

    def reload(self, state: Any) -> LocalContextFileResource:
        state_value: str = str(state.value)
        if state_value == "__undefined__":
            return LocalContextFileResource(self._source_path)

        for file_type in self.FILE_TYPES:
            candidate_path: Path = self._step_dir / f"{state_value}.{file_type}"
            if candidate_path.exists():
                return LocalContextFileResource(candidate_path)

        raise FileNotFoundError(f"Import step not found for '{state_value}' in '{self._step_dir}'.")

    def exists(self, state: Any) -> bool:
        if str(state.value) == "__undefined__":
            return True

        for file_type in self.FILE_TYPES:
            if (self._step_dir / f"{state.value}.{file_type}").exists():
                return True

        return False

    def write_text_file(
        self,
        state: Any,
        content: str,
        file_type: str = "txt",
        encoding: str = "utf-8",
    ) -> Path:
        target_path: Path = self._step_dir / f"{state.value}.{file_type}"
        target_path.write_text(content, encoding=encoding)
        return target_path

    def delete(self, state: Any) -> bool:
        if str(state.value) == "__undefined__":
            return False

        deleted: bool = False
        file_type: str
        for file_type in self.FILE_TYPES:
            candidate_path: Path = self._step_dir / f"{state.value}.{file_type}"
            if not candidate_path.exists():
                continue

            candidate_path.unlink()
            deleted = True

        return deleted
