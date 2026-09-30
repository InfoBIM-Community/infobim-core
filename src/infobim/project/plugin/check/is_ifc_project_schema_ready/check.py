from typing import Dict, List, Optional
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from infobim.project.domain.model.contract import ProjectContract

# This check is a standalone script: it runs from the command line without
# the CLI, the capability engine or any other check being importable. Its
# helpers are therefore its own, even where a neighbouring check verifies a
# neighbouring condition with helpers that read the same way. Sharing them
# would make one check the library of another, and a check that cannot run
# by itself has stopped being a check.

# The supported ifcOWL vocabularies and the IFC release each one identifies.
# The pairs are declared, never derived from the shape of a URI: a project
# typed with a vocabulary absent from this mapping is carrying a schema this
# contract does not support, and the check reports that instead of inventing
# a release URI for it. The runtime keeps its own copy of the same mapping,
# because this script has to run without importing the runtime.
_IFCOWL_VOCABULARIES: Dict[str, str] = {
    ProjectContract.IFCOWL_NAMESPACE: ProjectContract.DEFAULT_IFC_SCHEMA,
}


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


def _schema_from_ifc_project_type(value: URIRef) -> Optional[str]:
    uri: str = str(value).strip()
    namespace: str
    release_uri: str
    for namespace, release_uri in _IFCOWL_VOCABULARIES.items():
        if uri == f"{namespace}IfcProject":
            return release_uri

    return None


def _ifcowl_namespace_from_schema(schema: str) -> Optional[str]:
    if not isinstance(schema, str):
        return None

    schema_uri: str = schema.strip()
    namespace: str
    release_uri: str
    for namespace, release_uri in _IFCOWL_VOCABULARIES.items():
        if release_uri == schema_uri:
            return namespace

    return None


def _schema_values(graph: Graph, subject: URIRef) -> List[str]:
    schemas = {
        schema
        for class_uri in graph.objects(subject, RDF.type)
        if isinstance(class_uri, URIRef)
        for schema in [_schema_from_ifc_project_type(class_uri)]
        if schema is not None
    }
    return list(schemas)


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

    # Schema identity is the official buildingSMART RELEASE URI resolved from
    # the schema-specific ifcOWL rdf:type of IfcProject. No short schema token
    # and no parallel InfoBIM schema property are part of the contract.
    if len(_schema_values(graph, subjects[0])) != 1:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
