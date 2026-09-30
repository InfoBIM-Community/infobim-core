from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Standalone check. It imports no sibling check/hotfix and mutates nothing.
#
# The minimal InfoBIM spatial structure is a rooted IFC decomposition:
# IfcProject -> IfcSite -> IfcBuilding -> IfcBuildingStorey. More than one
# site/building/storey is allowed; what matters is that every entity in those
# levels has exactly one parent of the expected type and that at least one
# entity exists at each level.


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _by_type(model: Any, name: str) -> Optional[List[Any]]:
    try:
        return list(model.by_type(name))
    except Exception:
        return None


def _parent_map(model: Any) -> Optional[Dict[int, List[Any]]]:
    relations = _by_type(model, "IfcRelAggregates")
    if relations is None:
        return None

    parents: Dict[int, List[Any]] = {}
    for relation in relations:
        try:
            parent = relation.RelatingObject
            children = list(relation.RelatedObjects or [])
        except Exception:
            return None

        for child in children:
            try:
                parents.setdefault(child.id(), []).append(parent)
            except Exception:
                return None
    return parents


def _exact_parent(
    entity: Any,
    parents: Dict[int, List[Any]],
    expected_parent_ids: Set[int],
) -> bool:
    try:
        actual = parents.get(entity.id(), [])
    except Exception:
        return False
    if len(actual) != 1:
        return False
    try:
        return actual[0].id() in expected_parent_ids
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

    projects = _by_type(model, "IfcProject")
    sites = _by_type(model, "IfcSite")
    buildings = _by_type(model, "IfcBuilding")
    storeys = _by_type(model, "IfcBuildingStorey")
    parents = _parent_map(model)
    if None in (projects, sites, buildings, storeys, parents):
        return 1

    assert projects is not None
    assert sites is not None
    assert buildings is not None
    assert storeys is not None
    assert parents is not None

    if len(projects) != 1 or not sites or not buildings or not storeys:
        return 1

    project_ids = {projects[0].id()}
    site_ids = {site.id() for site in sites}
    building_ids = {building.id() for building in buildings}

    if not all(_exact_parent(site, parents, project_ids) for site in sites):
        return 1
    if not all(_exact_parent(building, parents, site_ids) for building in buildings):
        return 1
    if not all(_exact_parent(storey, parents, building_ids) for storey in storeys):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
