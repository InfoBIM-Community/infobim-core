from pathlib import Path
from typing import Any, List, Optional, Set

# Standalone hotfix. It imports no sibling check/hotfix.
#
# It only repairs context wiring. It never invents geometry: an
# IfcShapeRepresentation with no Items remains an error. Body representations
# are wired to one Body subcontext under the project's unique 3D Model context;
# other representations are wired directly to that Model context when their
# current context does not belong to the project.


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


def _model_context(project: Any) -> Optional[Any]:
    contexts = _direct_contexts(project)
    if contexts is None:
        return None
    contexts_3d = [context for context in contexts if _dimension(context) == 3]
    if len(contexts_3d) != 1:
        return None
    context = contexts_3d[0]
    try:
        wcs = getattr(context, "WorldCoordinateSystem", None)
        if (
            getattr(context, "ContextType", None) != "Model"
            or wcs is None
            or wcs.is_a() != "IfcAxis2Placement3D"
        ):
            return None
    except Exception:
        return None
    return context


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


def _belongs_to(context: Any, root: Any) -> bool:
    resolved = _root_context(context)
    if resolved is None:
        return False
    try:
        return resolved.id() == root.id()
    except Exception:
        return False


def _body_contexts(model: Any, root: Any) -> Optional[List[Any]]:
    try:
        subcontexts = list(model.by_type("IfcGeometricRepresentationSubContext"))
    except Exception:
        return None

    matches: List[Any] = []
    for context in subcontexts:
        try:
            if (
                getattr(context, "ParentContext", None) is not None
                and context.ParentContext.id() == root.id()
                and getattr(context, "ContextIdentifier", None) == "Body"
                and getattr(context, "ContextType", None) == "Model"
            ):
                matches.append(context)
        except Exception:
            return None
    return matches


def _body_context(model: Any, root: Any) -> Optional[Any]:
    contexts = _body_contexts(model, root)
    if contexts is None or len(contexts) > 1:
        return None
    if contexts:
        context = contexts[0]
        try:
            context.TargetView = "MODEL_VIEW"
        except Exception:
            return None
        return context

    try:
        return model.create_entity(
            "IfcGeometricRepresentationSubContext",
            ContextIdentifier="Body",
            ContextType="Model",
            ParentContext=root,
            TargetView="MODEL_VIEW",
        )
    except Exception:
        return None


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
        identifier = getattr(shape, "RepresentationIdentifier", None)
        if identifier == "Body":
            return (
                context.is_a() == "IfcGeometricRepresentationSubContext"
                and getattr(context, "ContextIdentifier", None) == "Body"
                and getattr(context, "ContextType", None) == "Model"
                and getattr(context, "TargetView", None) == "MODEL_VIEW"
            )
        return True
    except Exception:
        return False


def _all_valid(model: Any, project: Any) -> bool:
    try:
        project_context_ids = {
            context.id() for context in list(project.RepresentationContexts or [])
        }
        shapes = list(model.by_type("IfcShapeRepresentation"))
    except Exception:
        return False
    return all(_shape_is_valid(shape, project_context_ids) for shape in shapes)


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
    root = _model_context(project)
    if root is None:
        return 1

    try:
        shapes = list(model.by_type("IfcShapeRepresentation"))
    except Exception:
        return 1

    needs_body = any(
        getattr(shape, "RepresentationIdentifier", None) == "Body"
        for shape in shapes
    )
    body = _body_context(model, root) if needs_body else None
    if needs_body and body is None:
        return 1

    for shape in shapes:
        try:
            if not list(shape.Items or []):
                return 1
            identifier = getattr(shape, "RepresentationIdentifier", None)
            context = getattr(shape, "ContextOfItems", None)
            if identifier == "Body":
                shape.ContextOfItems = body
            elif context is None or not _belongs_to(context, root):
                shape.ContextOfItems = root
        except Exception:
            return 1

    try:
        model.write(str(model_path))
        verified = ifcopenshell.open(str(model_path))
        verified_projects = _projects(verified)
    except Exception:
        return 1

    if len(verified_projects) != 1:
        return 1
    return 0 if _all_valid(verified, verified_projects[0]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
