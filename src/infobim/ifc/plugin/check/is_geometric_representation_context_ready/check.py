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


def diagnose(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> List[str]:
    """
    Why the project does not own exactly one 3D Model context with a 3D world
    coordinate system: none when it does.
    """
    del project_path, container_path

    model_path = _resolve_path(ifc_model_path)
    if model_path is None or not model_path.is_file():
        return ["The IFC model was not given or does not exist."]

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(model_path))
    except Exception as error:
        return [f"The file does not read as an IFC STEP model: {error}"]

    projects = _projects(model)
    if len(projects) != 1:
        return [f"The model has {len(projects)} IfcProject entities; exactly one is required."]

    contexts = _direct_contexts(projects[0])
    if contexts is None:
        return ["The representation contexts of the IfcProject could not be read."]

    contexts_3d = [context for context in contexts if _dimension(context) == 3]
    if len(contexts_3d) != 1:
        return [
            f"The IfcProject owns {len(contexts_3d)} direct 3D geometric representation "
            "contexts; exactly one is required."
        ]

    if not _is_model_context(contexts_3d[0]):
        return [
            "The 3D context is not a Model context with a 3D world coordinate system "
            "(IfcAxis2Placement3D)."
        ]
    return []


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    return 1 if diagnose(project_path, ifc_model_path, container_path) else 0


if __name__ == "__main__":
    raise SystemExit(main())
