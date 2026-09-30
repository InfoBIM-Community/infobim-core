from pathlib import Path
from typing import Any, List, Optional

# Standalone check. It imports no sibling check/hotfix and mutates nothing.
#
# A geometric model is ready for 3D shape representation when its sole
# IfcProject owns exactly one direct 3D IfcGeometricRepresentationContext,
# that context is the Model context, and it carries a 3D WCS. A separate 2D
# context is allowed. Precision and TrueNorth are optional IFC attributes and
# therefore are not health requirements here.


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _projects(model: Any) -> List[Any]:
    try:
        return list(model.by_type("IfcProject"))
    except Exception:
        return []


def _direct_contexts(project: Any) -> Optional[List[Any]]:
    try:
        contexts = list(project.RepresentationContexts or [])
    except Exception:
        return None

    direct: List[Any] = []
    for context in contexts:
        try:
            if context.is_a() == "IfcGeometricRepresentationContext":
                direct.append(context)
        except Exception:
            return None
    return direct


def _dimension(context: Any) -> Optional[int]:
    try:
        value = getattr(context, "CoordinateSpaceDimension", None)
        return int(value) if value is not None else None
    except Exception:
        return None


def _is_model_context(context: Any) -> bool:
    try:
        if _dimension(context) != 3:
            return False
        if getattr(context, "ContextType", None) != "Model":
            return False
        world_coordinate_system = getattr(context, "WorldCoordinateSystem", None)
        return (
            world_coordinate_system is not None
            and world_coordinate_system.is_a() == "IfcAxis2Placement3D"
        )
    except Exception:
        return False


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    del project_path, container_path

    model_path = _resolve_path(ifc_model_path)
    if model_path is None or not model_path.is_file():
        return 1

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(model_path))
    except Exception:
        return 1

    projects = _projects(model)
    if len(projects) != 1:
        return 1

    contexts = _direct_contexts(projects[0])
    if contexts is None:
        return 1

    contexts_3d = [context for context in contexts if _dimension(context) == 3]
    if len(contexts_3d) != 1:
        return 1

    return 0 if _is_model_context(contexts_3d[0]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
