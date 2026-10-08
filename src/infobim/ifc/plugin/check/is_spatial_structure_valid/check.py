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



def _examples(entities: List[Any], limit: int = 5) -> str:
    listed = ", ".join(f"#{entity.id()}" for entity in entities[:limit])
    return listed + (", …" if len(entities) > limit else "")


def diagnose(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> List[str]:
    """
    What is missing or misplaced in the spatial structure
    IfcProject -> IfcSite -> IfcBuilding -> IfcBuildingStorey: one sentence per
    level. None when the structure is complete.
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

    projects = _by_type(model, "IfcProject")
    sites = _by_type(model, "IfcSite")
    buildings = _by_type(model, "IfcBuilding")
    storeys = _by_type(model, "IfcBuildingStorey")
    parents = _parent_map(model)
    if None in (projects, sites, buildings, storeys, parents):
        return ["The spatial elements or the IfcRelAggregates of the model could not be read."]

    assert projects is not None
    assert sites is not None
    assert buildings is not None
    assert storeys is not None
    assert parents is not None

    findings: List[str] = []
    if len(projects) != 1:
        findings.append(f"The model has {len(projects)} IfcProject entities; exactly one is required.")
    for name, found in (("IfcSite", sites), ("IfcBuilding", buildings), ("IfcBuildingStorey", storeys)):
        if not found:
            findings.append(f"The model has no {name}.")
    if len(projects) != 1:
        return findings

    levels = (
        ("IfcSite", sites, {projects[0].id()}, "the IfcProject"),
        ("IfcBuilding", buildings, {site.id() for site in sites}, "an IfcSite"),
        ("IfcBuildingStorey", storeys, {building.id() for building in buildings}, "an IfcBuilding"),
    )
    for name, entities, parent_ids, expected in levels:
        misplaced = [entity for entity in entities if not _exact_parent(entity, parents, parent_ids)]
        if misplaced:
            findings.append(
                f"{len(misplaced)} of {len(entities)} {name} entities do not have exactly one "
                f"parent, {expected} ({_examples(misplaced)})."
            )
    return findings


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    return 1 if diagnose(project_path, ifc_model_path, container_path) else 0


if __name__ == "__main__":
    raise SystemExit(main())
