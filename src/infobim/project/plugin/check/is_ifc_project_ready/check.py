from pathlib import Path
from typing import List, Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from infobim.project.domain.model.contract import ProjectContract


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _load_graph(file_path: Path) -> Optional[Graph]:
    graph: Graph = Graph()
    try:
        graph.parse(str(file_path), format="turtle")
    except Exception:
        return None

    return graph


def _ifc_project_path(dataset_path: Path) -> Path:
    return (
        dataset_path
        / ProjectContract.PAYLOAD_DIRECTORY_NAME
        / ProjectContract.TRIPLE_DIRECTORY_NAME
        / ProjectContract.IFC_PROJECT_FILE_NAME
    )


def _is_ifcowl_term(value: URIRef, local_name: str) -> bool:
    uri: str = str(value)
    return (
        uri.startswith(ProjectContract.IFCOWL_NAMESPACE_BASE)
        and uri.endswith(local_name)
    )


def _is_ifc_project_class(value: URIRef) -> bool:
    return _is_ifcowl_term(value, "#IfcProject")


def _ifc_project_subjects(graph: Graph) -> List[URIRef]:
    subjects = {
        subject
        for subject, class_uri in graph.subject_objects(RDF.type)
        if isinstance(subject, URIRef)
        and isinstance(class_uri, URIRef)
        and _is_ifc_project_class(class_uri)
    }
    return list(subjects)


def _ifcowl_property_values(
    graph: Graph,
    subject: URIRef,
    local_name: str,
) -> List[object]:
    values: List[object] = []
    for predicate, value in graph.predicate_objects(subject):
        if isinstance(predicate, URIRef) and _is_ifcowl_term(
            predicate,
            f"#{local_name}",
        ):
            values.append(value)

    return values


def _has_global_id(graph: Graph, subject: URIRef) -> bool:
    return any(
        str(value).strip()
        for value in _ifcowl_property_values(
            graph,
            subject,
            "globalId_IfcRoot",
        )
    )


def main(project_path: Optional[str] = None) -> int:
    resolved_project_path: Optional[Path] = _resolve_path(project_path)
    if resolved_project_path is None:
        return 1

    dataset_path: Path = resolved_project_path / ProjectContract.DATASET_NAME
    if not dataset_path.is_dir():
        return 1

    ifc_project_path: Path = _ifc_project_path(dataset_path)
    if not ifc_project_path.is_file():
        return 1

    graph: Optional[Graph] = _load_graph(ifc_project_path)
    if graph is None:
        return 1

    subjects: List[URIRef] = _ifc_project_subjects(graph)
    if len(subjects) != 1:
        return 1

    if not _has_global_id(graph, subjects[0]):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
