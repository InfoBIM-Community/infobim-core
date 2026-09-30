from pathlib import Path
from typing import Any, List, Optional, Set

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


def _product_valid(product: Any) -> bool:
    if not _requires_placement(product):
        return True
    try:
        placement = product.ObjectPlacement
    except Exception:
        return False
    if placement is None:
        return False
    try:
        if placement.is_a() == "IfcLocalPlacement":
            return _local_placement_valid(placement)
        return bool(placement.is_a())
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

    products = _products(model)
    if products is None:
        return 1

    return 0 if all(_product_valid(product) for product in products) else 1


if __name__ == "__main__":
    raise SystemExit(main())
