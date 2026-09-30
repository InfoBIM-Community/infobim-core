from pathlib import Path
from typing import Any, List, Optional

# Standalone hotfix. It imports no sibling check/hotfix.
#
# It repairs only the unambiguous 3D model-context case: if there is no 3D
# context it creates one; if there is exactly one it normalises that context.
# More than one 3D direct context is ambiguous and is never merged or deleted.


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
    result: List[Any] = []
    for context in contexts:
        try:
            if context.is_a() == "IfcGeometricRepresentationContext":
                result.append(context)
        except Exception:
            return None
    return result


def _dimension(context: Any) -> Optional[int]:
    try:
        value = getattr(context, "CoordinateSpaceDimension", None)
        return int(value) if value is not None else None
    except Exception:
        return None


def _is_ready(project: Any) -> bool:
    contexts = _direct_contexts(project)
    if contexts is None:
        return False
    contexts_3d = [context for context in contexts if _dimension(context) == 3]
    if len(contexts_3d) != 1:
        return False
    context = contexts_3d[0]
    try:
        wcs = getattr(context, "WorldCoordinateSystem", None)
        return (
            getattr(context, "ContextType", None) == "Model"
            and wcs is not None
            and wcs.is_a() == "IfcAxis2Placement3D"
        )
    except Exception:
        return False


def _new_wcs(model: Any) -> Any:
    origin = model.create_entity(
        "IfcCartesianPoint",
        Coordinates=(0.0, 0.0, 0.0),
    )
    return model.create_entity(
        "IfcAxis2Placement3D",
        Location=origin,
    )


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
    project = projects[0]

    contexts = _direct_contexts(project)
    if contexts is None:
        return 1
    contexts_3d = [context for context in contexts if _dimension(context) == 3]
    if len(contexts_3d) > 1:
        return 1

    try:
        if contexts_3d:
            context = contexts_3d[0]
            context.ContextType = "Model"
            context.CoordinateSpaceDimension = 3
            wcs = getattr(context, "WorldCoordinateSystem", None)
            if wcs is None or wcs.is_a() != "IfcAxis2Placement3D":
                context.WorldCoordinateSystem = _new_wcs(model)
        else:
            context = model.create_entity(
                "IfcGeometricRepresentationContext",
                ContextIdentifier="Model",
                ContextType="Model",
                CoordinateSpaceDimension=3,
                Precision=1.0e-5,
                WorldCoordinateSystem=_new_wcs(model),
            )
            existing = list(project.RepresentationContexts or [])
            project.RepresentationContexts = tuple(existing + [context])

        model.write(str(model_path))
        verified = ifcopenshell.open(str(model_path))
        verified_projects = _projects(verified)
    except Exception:
        return 1

    if len(verified_projects) != 1:
        return 1
    return 0 if _is_ready(verified_projects[0]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
