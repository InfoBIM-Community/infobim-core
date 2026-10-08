from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Standalone check. It imports no sibling check/hotfix and mutates nothing.
#
# Spatial elements and represented products need an ObjectPlacement. Local
# placements must have a valid relative placement and a finite, acyclic
# PlacementRelTo chain. Other IFC placement strategies are accepted as model
# facts rather than being rewritten to local placements.


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _products(model: Any) -> Optional[List[Any]]:
    try:
        return list(model.by_type("IfcProduct"))
    except Exception:
        return None


def _requires_placement(product: Any) -> bool:
    try:
        if product.is_a("IfcSpatialElement"):
            return True
        return getattr(product, "Representation", None) is not None
    except Exception:
        return False


def _local_placement_valid(placement: Any) -> bool:
    seen: Set[int] = set()
    current = placement
    while current is not None:
        try:
            entity_id = current.id()
            if entity_id in seen:
                return False
            seen.add(entity_id)
            entity_type = current.is_a()
        except Exception:
            return False

        if entity_type != "IfcLocalPlacement":
            return True

        try:
            relative = current.RelativePlacement
            if relative is None or relative.is_a() not in {
                "IfcAxis2Placement2D",
                "IfcAxis2Placement3D",
            }:
                return False
            current = current.PlacementRelTo
        except Exception:
            return False

    return True



def _examples(entities: List[Any], limit: int = 5) -> str:
    listed = ", ".join(f"#{entity.id()}" for entity in entities[:limit])
    return listed + (", …" if len(entities) > limit else "")


def _product_problem(product: Any) -> Optional[str]:
    """Why the product's placement is not valid, None when it is."""
    if not _requires_placement(product):
        return None
    try:
        placement = product.ObjectPlacement
    except Exception:
        return "its placement cannot be read"
    if placement is None:
        return "it has no ObjectPlacement"
    try:
        if placement.is_a() == "IfcLocalPlacement":
            if not _local_placement_valid(placement):
                return "its local placement chain is invalid or cyclic"
            return None
        return None if bool(placement.is_a()) else "its placement is of an unknown type"
    except Exception:
        return "its placement cannot be read"


def _product_valid(product: Any) -> bool:
    return _product_problem(product) is None


def diagnose(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> List[str]:
    """
    The products that need an ObjectPlacement and do not have a valid one,
    grouped by what is wrong, with the first few ids. None when all do.
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

    products = _products(model)
    if products is None:
        return ["The products of the model could not be read."]

    by_problem: Dict[str, List[Any]] = {}
    for product in products:
        problem = _product_problem(product)
        if problem is not None:
            by_problem.setdefault(problem, []).append(product)
    return [
        f"{len(invalid)} of {len(products)} products are invalid: {problem} ({_examples(invalid)})."
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
