from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Standalone hotfix. It imports no sibling check/hotfix.
#
# It fills missing placements and missing RelativePlacement values. It never
# rewrites a non-local IFC placement strategy and never tries to break an
# existing placement cycle by guessing which relationship should be removed.


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


def _origin_placement(model: Any, parent: Optional[Any]) -> Any:
    point = model.create_entity(
        "IfcCartesianPoint",
        Coordinates=(0.0, 0.0, 0.0),
    )
    axis = model.create_entity(
        "IfcAxis2Placement3D",
        Location=point,
    )
    return model.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=parent,
        RelativePlacement=axis,
    )


def _aggregate_parent_map(model: Any) -> Optional[Dict[int, Any]]:
    try:
        relations = list(model.by_type("IfcRelAggregates"))
    except Exception:
        return None

    parents: Dict[int, Any] = {}
    for relation in relations:
        try:
            parent = relation.RelatingObject
            for child in list(relation.RelatedObjects or []):
                child_id = child.id()
                if child_id in parents and parents[child_id].id() != parent.id():
                    return None
                parents[child_id] = parent
        except Exception:
            return None
    return parents


def _containment_parent_map(model: Any) -> Optional[Dict[int, Any]]:
    try:
        relations = list(model.by_type("IfcRelContainedInSpatialStructure"))
    except Exception:
        return None

    parents: Dict[int, Any] = {}
    for relation in relations:
        try:
            parent = relation.RelatingStructure
            for child in list(relation.RelatedElements or []):
                child_id = child.id()
                if child_id in parents and parents[child_id].id() != parent.id():
                    return None
                parents[child_id] = parent
        except Exception:
            return None
    return parents


def _parent_placement(
    product: Any,
    aggregate_parents: Dict[int, Any],
    containment_parents: Dict[int, Any],
) -> Optional[Any]:
    try:
        product_id = product.id()
    except Exception:
        return None

    parent = containment_parents.get(product_id) or aggregate_parents.get(product_id)
    if parent is None:
        return None
    try:
        return getattr(parent, "ObjectPlacement", None)
    except Exception:
        return None


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
    aggregate_parents = _aggregate_parent_map(model)
    containment_parents = _containment_parent_map(model)
    if products is None or aggregate_parents is None or containment_parents is None:
        return 1

    # Spatial parents must be repaired before their children so newly created
    # local placements can be relative to the parent placement when available.
    def depth(product: Any) -> int:
        seen: Set[int] = set()
        current = product
        value = 0
        while current is not None:
            try:
                current_id = current.id()
                if current_id in seen:
                    return 10**6
                seen.add(current_id)
                parent = aggregate_parents.get(current_id)
            except Exception:
                return 10**6
            if parent is None:
                return value
            current = parent
            value += 1
        return value

    for product in sorted(products, key=depth):
        if not _requires_placement(product):
            continue
        try:
            placement = product.ObjectPlacement
        except Exception:
            return 1

        if placement is None:
            try:
                product.ObjectPlacement = _origin_placement(
                    model,
                    _parent_placement(
                        product,
                        aggregate_parents,
                        containment_parents,
                    ),
                )
            except Exception:
                return 1
            continue

        try:
            if placement.is_a() != "IfcLocalPlacement":
                continue
        except Exception:
            return 1

        if _local_placement_valid(placement):
            continue

        try:
            relative = placement.RelativePlacement
            if relative is None:
                point = model.create_entity(
                    "IfcCartesianPoint",
                    Coordinates=(0.0, 0.0, 0.0),
                )
                placement.RelativePlacement = model.create_entity(
                    "IfcAxis2Placement3D",
                    Location=point,
                )
            else:
                # An invalid non-null relative placement or a cycle is not
                # repaired by replacement because that would discard intent.
                return 1
        except Exception:
            return 1

    try:
        model.write(str(model_path))
        verified = ifcopenshell.open(str(model_path))
        verified_products = _products(verified)
    except Exception:
        return 1

    if verified_products is None:
        return 1
    return 0 if all(_product_valid(product) for product in verified_products) else 1


if __name__ == "__main__":
    raise SystemExit(main())
