import os
from pathlib import Path
from typing import Optional


def normalize_cli_path(raw_path: str) -> str:
    if not isinstance(raw_path, str):
        raise ValueError("Path argument must be a string.")

    normalized_path: str = raw_path.strip().strip("'\"").strip()

    if not normalized_path:
        raise ValueError("Path argument cannot be empty.")

    if "\x00" in normalized_path:
        raise ValueError("Path argument contains a null character.")

    if os.name == "nt":
        invalid_characters: set[str] = set('<>"|?*')
        path_without_drive: str = normalized_path
        if len(path_without_drive) >= 2 and path_without_drive[1] == ":":
            path_without_drive = path_without_drive[2:]

        invalid_character: Optional[str] = next(
            (
                character
                for character in path_without_drive
                if character in invalid_characters or ord(character) < 32
            ),
            None,
        )
        if invalid_character is not None:
            raise ValueError(
                f"Path argument contains an invalid Windows character: {invalid_character!r}.",
            )

    return normalized_path


def resolve_cli_input_path(raw_path: str, root_path: Optional[str] = None) -> Path:
    candidate_path: Path = Path(normalize_cli_path(raw_path)).expanduser()
    if candidate_path.is_absolute():
        return candidate_path.resolve()

    if isinstance(root_path, str) and root_path.strip():
        return (Path(root_path).expanduser().resolve() / candidate_path).resolve()

    return candidate_path.resolve()
