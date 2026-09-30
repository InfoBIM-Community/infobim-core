from pathlib import Path
from typing import List, Optional

from infobim.project.plugin.check.is_ifc_project_schema_ready.hotfix import (
    main as ensure_ifc_project_schema,
)
from infobim.project.plugin.check.is_ifc_project_refreshed.check import (
    main as check_ifc_project_refreshed,
)


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def main(
    project_path: Optional[str] = None,
    dataset_paths: Optional[List[str]] = None,
) -> int:
    resolved_project_path: Optional[Path] = _resolve_path(project_path)
    if resolved_project_path is None:
        return 1

    schema_exit_code: int = ensure_ifc_project_schema(
        project_path=str(resolved_project_path),
        dataset_paths=dataset_paths,
    )
    if schema_exit_code != 0:
        return schema_exit_code

    return check_ifc_project_refreshed(project_path=str(resolved_project_path))


if __name__ == "__main__":
    raise SystemExit(main())
