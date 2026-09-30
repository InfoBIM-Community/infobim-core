from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Standalone hotfix. It imports no sibling check/hotfix.
#
# It creates missing Site/Building/Storey levels only when the parent is
# unambiguous and adds missing IfcRelAggregates links. It never deletes,
# merges, reparents or chooses among competing parents.


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


def _link(model: Any, parent: Any, child: Any) -> bool:
    try:
        import ifcopenshell.guid

        model.create_entity(
            "IfcRelAggregates",
            GlobalId=ifcopenshell.guid.new(),
            RelatingObject=parent,
            RelatedObjects=(child,),
        )
        return True
    except Exception:
        return False


def _ensure_parent(
    model: Any,
    entity: Any,
    parents: Dict[int, List[Any]],
    expected_parents: List[Any],
) -> bool:
    try:
        actual = parents.get(entity.id(), [])
    except Exception:
        return False

    if len(actual) > 1:
        return False
    if len(actual) == 1:
        try:
            expected_ids = {parent.id() for parent in expected_parents}
            return actual[0].id() in expected_ids
        except Exception:
            return False

    if len(expected_parents) != 1:
        return False
    if not _link(model, expected_parents[0], entity):
        return False
    parents.setdefault(entity.id(), []).append(expected_parents[0])
    return True


def _new_root(model: Any, ifc_class: str, name: str) -> Optional[Any]:
    try:
        import ifcopenshell.guid

        return model.create_entity(
            ifc_class,
            GlobalId=ifcopenshell.guid.new(),
            Name=name,
        )
    except Exception:
        return None


def _valid(model: Any) -> bool:
    projects = _by_type(model, "IfcProject")
    sites = _by_type(model, "IfcSite")
    buildings = _by_type(model, "IfcBuilding")
    storeys = _by_type(model, "IfcBuildingStorey")
    parents = _parent_map(model)
    if None in (projects, sites, buildings, storeys, parents):
        return False

    assert projects is not None
    assert sites is not None
    assert buildings is not None
    assert storeys is not None
    assert parents is not None

    if len(projects) != 1 or not sites or not buildings or not storeys:
        return False

    project_ids: Set[int] = {projects[0].id()}
    site_ids: Set[int] = {site.id() for site in sites}
    building_ids: Set[int] = {building.id() for building in buildings}

    for entity, expected_ids in (
        *[(site, project_ids) for site in sites],
        *[(building, site_ids) for building in buildings],
        *[(storey, building_ids) for storey in storeys],
    ):
        actual = parents.get(entity.id(), [])
        if len(actual) != 1 or actual[0].id() not in expected_ids:
            return False
    return True


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
    if projects is None or len(projects) != 1:
        return 1
    project = projects[0]

    parents = _parent_map(model)
    if parents is None:
        return 1

    sites = _by_type(model, "IfcSite")
    if sites is None:
        return 1
    if not sites:
        site = _new_root(model, "IfcSite", "Site")
        if site is None or not _link(model, project, site):
            return 1
        sites = [site]
        parents.setdefault(site.id(), []).append(project)
    else:
        for site in sites:
            if not _ensure_parent(model, site, parents, [project]):
                return 1

    buildings = _by_type(model, "IfcBuilding")
    if buildings is None:
        return 1
    if not buildings:
        if len(sites) != 1:
            return 1
        building = _new_root(model, "IfcBuilding", "Building")
        if building is None or not _link(model, sites[0], building):
            return 1
        buildings = [building]
        parents.setdefault(building.id(), []).append(sites[0])
    else:
        for building in buildings:
            if not _ensure_parent(model, building, parents, sites):
                return 1

    storeys = _by_type(model, "IfcBuildingStorey")
    if storeys is None:
        return 1
    if not storeys:
        if len(buildings) != 1:
            return 1
        storey = _new_root(model, "IfcBuildingStorey", "Storey")
        if storey is None or not _link(model, buildings[0], storey):
            return 1
        storeys = [storey]
        parents.setdefault(storey.id(), []).append(buildings[0])
    else:
        for storey in storeys:
            if not _ensure_parent(model, storey, parents, buildings):
                return 1

    try:
        model.write(str(model_path))
        verified = ifcopenshell.open(str(model_path))
    except Exception:
        return 1

    return 0 if _valid(verified) else 1


if __name__ == "__main__":
    raise SystemExit(main())
