from pathlib import Path
from typing import Any, List, Optional, Set

# Standalone check. It imports no sibling check/hotfix and mutates nothing.
#
# Every IfcShapeRepresentation must point at a geometric representation
# context that ultimately belongs to the sole IfcProject and must contain at
# least one representation item. Body representations specifically belong to
# a Body/Model/MODEL_VIEW subcontext. A model with no shape representations
# passes: geometry may simply not have been created yet.


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _projects(model: Any) -> List[Any]:
    try:
        return list(model.by_type("IfcProject"))
    except Exception:
        return []


def _project_context_ids(project: Any) -> Optional[Set[int]]:
    try:
        contexts = list(project.RepresentationContexts or [])
    except Exception:
        return None

    ids: Set[int] = set()
    for context in contexts:
        try:
            ids.add(context.id())
        except Exception:
            return None
    return ids


def _root_context(context: Any) -> Optional[Any]:
    current = context
    seen: Set[int] = set()
    while current is not None:
        try:
            entity_id = current.id()
            if entity_id in seen:
                return None
            seen.add(entity_id)
            entity_type = current.is_a()
        except Exception:
            return None

        if entity_type == "IfcGeometricRepresentationContext":
            return current
        if entity_type != "IfcGeometricRepresentationSubContext":
            return None

        try:
            current = current.ParentContext
        except Exception:
            return None

    return None


def _body_context_valid(context: Any) -> bool:
    try:
        return (
            context.is_a() == "IfcGeometricRepresentationSubContext"
            and getattr(context, "ContextIdentifier", None) == "Body"
            and getattr(context, "ContextType", None) == "Model"
            and getattr(context, "TargetView", None) == "MODEL_VIEW"
        )
    except Exception:
        return False


def _shape_is_valid(shape: Any, project_context_ids: Set[int]) -> bool:
    try:
        context = shape.ContextOfItems
        items = list(shape.Items or [])
    except Exception:
        return False

    if context is None or not items:
        return False

    root = _root_context(context)
    if root is None:
        return False

    try:
        if root.id() not in project_context_ids:
            return False
        if getattr(shape, "RepresentationIdentifier", None) == "Body":
            return _body_context_valid(context)
        return True
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

    context_ids = _project_context_ids(projects[0])
    if context_ids is None:
        return 1

    try:
        shapes = list(model.by_type("IfcShapeRepresentation"))
    except Exception:
        return 1

    return 0 if all(_shape_is_valid(shape, context_ids) for shape in shapes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
