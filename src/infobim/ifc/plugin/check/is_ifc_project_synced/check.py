from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from infobim.project.domain.model.contract import ProjectContract

# Standalone health check. It imports no sibling check/hotfix and performs no
# mutation. The InfoBIM semantic IfcProject descriptor is the source of truth;
# the STEP model is healthy for this concern only when it carries exactly one
# IfcProject and that entity mirrors the descriptor's project identity and
# descriptive attributes.

_PROJECT_ATTRIBUTE_MAP: Dict[str, str] = {
    "globalId_IfcRoot": "GlobalId",
    "name_IfcRoot": "Name",
    "description_IfcRoot": "Description",
    "objectType_IfcObject": "ObjectType",
    "longName_IfcContext": "LongName",
    "phase_IfcContext": "Phase",
}


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _project_path(
    project_path: Optional[str],
    container_path: Optional[str],
) -> Optional[Path]:
    return _resolve_path(project_path) or _resolve_path(container_path)


def _descriptor_path(project_path: Path) -> Path:
    return (
        project_path
        / ProjectContract.DATASET_NAME
        / ProjectContract.PAYLOAD_DIRECTORY_NAME
        / ProjectContract.TRIPLE_DIRECTORY_NAME
        / ProjectContract.IFC_PROJECT_FILE_NAME
    )


def _load_graph(path: Path) -> Optional[Graph]:
    if not path.is_file():
        return None
    graph = Graph()
    try:
        graph.parse(str(path), format="turtle")
    except Exception:
        return None
    return graph


def _is_ifc_project_class(value: object) -> bool:
    if not isinstance(value, URIRef):
        return False
    uri = str(value)
    return (
        uri.startswith(ProjectContract.IFCOWL_NAMESPACE_BASE)
        and uri.endswith("#IfcProject")
    )


def _project_subjects(graph: Graph) -> List[URIRef]:
    return list(
        {
            subject
            for subject, class_uri in graph.subject_objects(RDF.type)
            if isinstance(subject, URIRef) and _is_ifc_project_class(class_uri)
        }
    )


def _property_values(
    graph: Graph,
    subject: URIRef,
    local_name: str,
) -> List[object]:
    suffix = f"#{local_name}"
    return [
        value
        for predicate, value in graph.predicate_objects(subject)
        if isinstance(predicate, URIRef)
        and str(predicate).startswith(ProjectContract.IFCOWL_NAMESPACE_BASE)
        and str(predicate).endswith(suffix)
    ]


def _source_value(
    graph: Graph,
    subject: URIRef,
    local_name: str,
    *,
    required: bool,
) -> Tuple[bool, Optional[str]]:
    values = _property_values(graph, subject, local_name)
    if len(values) > 1:
        return False, None
    if not values:
        return (False, None) if required else (True, None)

    value = str(values[0])
    if required and not value.strip():
        return False, None
    return True, value


def _source_attributes(project_path: Path) -> Optional[Dict[str, Optional[str]]]:
    graph = _load_graph(_descriptor_path(project_path))
    if graph is None:
        return None

    subjects = _project_subjects(graph)
    if len(subjects) != 1:
        return None

    source: Dict[str, Optional[str]] = {}
    for local_name, attribute_name in _PROJECT_ATTRIBUTE_MAP.items():
        ok, value = _source_value(
            graph,
            subjects[0],
            local_name,
            required=(attribute_name == "GlobalId"),
        )
        if not ok:
            return None
        source[attribute_name] = value

    return source


def _entity_value(entity: Any, attribute_name: str) -> Optional[str]:
    try:
        value = getattr(entity, attribute_name)
    except Exception:
        return None
    if value is None:
        return None
    return str(value)


def _is_synced(model: Any, source: Dict[str, Optional[str]]) -> bool:
    try:
        projects = list(model.by_type("IfcProject"))
    except Exception:
        return False

    if len(projects) != 1:
        return False

    project = projects[0]
    return all(
        _entity_value(project, attribute_name) == expected_value
        for attribute_name, expected_value in source.items()
    )


def main(
    project_path: Optional[str] = None,
    ifc_model_path: Optional[str] = None,
    container_path: Optional[str] = None,
) -> int:
    resolved_project_path = _project_path(project_path, container_path)
    resolved_model_path = _resolve_path(ifc_model_path)
    if resolved_project_path is None or resolved_model_path is None:
        return 1
    if not resolved_model_path.is_file():
        return 1

    source = _source_attributes(resolved_project_path)
    if source is None:
        return 1

    try:
        import ifcopenshell

        model = ifcopenshell.open(str(resolved_model_path))
    except Exception:
        return 1

    return 0 if _is_synced(model, source) else 1


if __name__ == "__main__":
    raise SystemExit(main())
