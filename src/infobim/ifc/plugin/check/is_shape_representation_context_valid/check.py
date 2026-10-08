from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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



def _examples(entities: List[Any], limit: int = 5) -> str:
    listed = ", ".join(f"#{entity.id()}" for entity in entities[:limit])
    return listed + (", …" if len(entities) > limit else "")


def _shape_problem(shape: Any, project_context_ids: Set[int]) -> Optional[str]:
    """Why the shape representation is not valid, None when it is."""
    try:
        context = shape.ContextOfItems
        items = list(shape.Items or [])
    except Exception:
        return "its context or items cannot be read"

    if context is None:
        return "it has no context"
    if not items:
        return "it has no representation item"

    root = _root_context(context)
    if root is None:
        return "its context does not lead to a geometric representation context"

    try:
        if root.id() not in project_context_ids:
            return "its context does not belong to the IfcProject"
        if getattr(shape, "RepresentationIdentifier", None) == "Body" and not _body_context_valid(context):
            return "a Body representation is not in a Body/Model/MODEL_VIEW sub-context"
    except Exception:
        return "its context cannot be read"
    return None


def _shape_is_valid(shape: Any, project_context_ids: Set[int]) -> bool:
    return _shape_problem(shape, project_context_ids) is None


def diagnose(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> List[str]:
    """
    The shape representations that do not reference a valid context of the
    IfcProject, grouped by what is wrong with them, with the first few ids.
    None when every one does (or the model has none).
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

    context_ids = _project_context_ids(projects[0])
    if context_ids is None:
        return ["The representation contexts of the IfcProject could not be read."]

    try:
        shapes = list(model.by_type("IfcShapeRepresentation"))
    except Exception:
        return ["The shape representations of the model could not be read."]

    by_problem: Dict[str, List[Any]] = {}
    for shape in shapes:
        problem = _shape_problem(shape, context_ids)
        if problem is not None:
            by_problem.setdefault(problem, []).append(shape)
    return [
        f"{len(invalid)} of {len(shapes)} shape representations are invalid: {problem} ({_examples(invalid)})."
        for problem, invalid in by_problem.items()
    ]


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    return 1 if diagnose(project_path, ifc_model_path, container_path) else 0


if __name__ == "__main__":
    raise SystemExit(main())
