"""Check declaration, writability and readability in the model's own IFC schema."""

import os
from typing import List, Optional, Set
from pathlib import Path

from infobim.ifc.adapter.models import IfcProjectModels


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _project_path(
    project_path: Optional[str],
    container_path: Optional[str],
) -> Optional[Path]:
    return _resolve_path(project_path) or _resolve_path(container_path)


def _crate_file_ids(project_path: Path) -> Optional[Set[str]]:
    return IfcProjectModels.declared_paths(project_path)


def _is_declared(project_path: Path, model_path: Path) -> bool:
    if not model_path.is_relative_to(project_path):
        return False

    file_ids: Optional[Set[str]] = _crate_file_ids(project_path)
    if file_ids is None:
        return False

    return str(model_path.relative_to(project_path)) in file_ids


def diagnose(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> List[str]:
    """
    Why the model is not healthy: one sentence per failed condition that could
    be told apart, none when it is healthy. Stops at the first failure that
    makes the next conditions meaningless.
    """
    resolved_project_path: Optional[Path] = _project_path(
        project_path,
        container_path,
    )
    resolved_model_path: Optional[Path] = _resolve_path(ifc_model_path)
    if resolved_project_path is None or resolved_model_path is None:
        return ["The project or the IFC model was not given."]

    if not resolved_model_path.is_file():
        return [f"The IFC file {resolved_model_path.name} does not exist."]

    findings: List[str] = []
    if not _is_declared(resolved_project_path, resolved_model_path):
        findings.append("The project's RO-Crate does not declare this model.")

    if not os.access(resolved_model_path, os.W_OK):
        findings.append("The IFC file is not writable.")

    # Imported here, not at module level: importing this module (as the
    # project refresh machine does) must not require ifcopenshell, which is
    # unavailable in some runtimes (e.g. Pyodide). Only checking a model does.
    import ifcopenshell

    try:
        ifcopenshell.open(str(resolved_model_path))
    except Exception as error:
        findings.append(f"The file does not read as an IFC STEP model: {error}")

    return findings


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    return 1 if diagnose(project_path, ifc_model_path, container_path) else 0


if __name__ == "__main__":
    raise SystemExit(main())
