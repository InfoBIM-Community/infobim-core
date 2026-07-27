from pathlib import Path
from typing import Optional


def resolve_cli_input_path(raw_path: str, root_path: Optional[str] = None) -> Path:
    candidate_path: Path = Path(raw_path).expanduser()
    if candidate_path.is_absolute():
        return candidate_path.resolve()

    if isinstance(root_path, str) and root_path.strip():
        return (Path(root_path).expanduser().resolve() / candidate_path).resolve()

    return candidate_path.resolve()
