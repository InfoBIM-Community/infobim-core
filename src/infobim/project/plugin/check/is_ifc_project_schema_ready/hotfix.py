from typing import Dict, List, Optional
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from infobim.project.domain.model.contract import ProjectContract

# This hotfix is a standalone script: it runs from the command line without
# the CLI, the capability engine or any other check being importable. Its
# helpers are therefore its own, and it verifies its own result instead of
# calling the check beside it, so neither file is the other's library.

# The supported ifcOWL vocabularies and the IFC release each one identifies.
# The pairs are declared, never derived from the shape of a URI: a project
# typed with a vocabulary absent from this mapping is carrying a schema this
# contract does not support, and the script reports that instead of inventing
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


def _declared_ifc_project_types(graph: Graph, subject: URIRef) -> List[URIRef]:
    return [
        class_uri
        for class_uri in graph.objects(subject, RDF.type)
        if isinstance(class_uri, URIRef) and _is_ifc_project_class(class_uri)
    ]


def _schema_values(graph: Graph, subject: URIRef) -> List[str]:
    schemas = {
        schema
        for class_uri in graph.objects(subject, RDF.type)
        if isinstance(class_uri, URIRef)
        for schema in [_schema_from_ifc_project_type(class_uri)]
        if schema is not None
    }
    return list(schemas)


def _is_schema_ready(project_path: Path) -> bool:
    """
    Report whether the project resolves to exactly one IFC schema.
    """
    dataset_path: Path = project_path / ProjectContract.DATASET_NAME
    if not dataset_path.is_dir():
        return False

    ifc_project_path: Path = _ifc_project_path(dataset_path)
    if not ifc_project_path.is_file():
        return False

    graph: Optional[Graph] = _load_graph(ifc_project_path)
    if graph is None:
        return False

    subjects: List[URIRef] = _ifc_project_subjects(graph)
    if len(subjects) != 1:
        return False

    return len(_schema_values(graph, subjects[0])) == 1


def main(
    project_path: Optional[str] = None,
    schema: Optional[str] = None,
) -> int:
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

    subject: URIRef = subjects[0]
    existing_schemas: List[str] = _schema_values(graph, subject)
    if len(existing_schemas) > 1:
        return 1

    if existing_schemas:
        return 0 if _is_schema_ready(resolved_project_path) else 1

    # The IfcProject is typed with a vocabulary this contract does not
    # register. That is existing schema data of an unsupported schema, and
    # the default release URI is a value for writing schema information that
    # is missing, never a reading of schema information that is unknown:
    # retyping it here would silently reinterpret the project as IFC 4.3.
    if _declared_ifc_project_types(graph, subject):
        return 1

    schema_uri: str = (
        schema.strip()
        if isinstance(schema, str) and schema.strip()
        else ProjectContract.DEFAULT_IFC_SCHEMA
    )
    namespace: Optional[str] = _ifcowl_namespace_from_schema(schema_uri)
    if namespace is None:
        return 1

    canonical_type: URIRef = URIRef(f"{namespace}IfcProject")

    for class_uri in list(graph.objects(subject, RDF.type)):
        if (
            isinstance(class_uri, URIRef)
            and _is_ifc_project_class(class_uri)
        ):
            graph.remove((subject, RDF.type, class_uri))

    graph.add((subject, RDF.type, canonical_type))
    graph.bind("ifcowl", Namespace(namespace), replace=True)

    try:
        ifc_project_path.write_bytes(
            graph.serialize(format="turtle", encoding="utf-8")
        )
    except OSError:
        return 1

    return 0 if _is_schema_ready(resolved_project_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
