import uuid
from typing import Dict, List, Optional
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

from infobim.project.domain.model.contract import ProjectContract
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StorageNamespaceBootstrap,
)

# This hotfix is a standalone script: it runs from the command line without
# the CLI, the capability engine or any other check being importable. Its
# helpers are therefore its own, and it verifies its own result instead of
# calling the checks beside it, so no check is the library of another file.

_IFC64_ALPHABET: str = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
)
_IFC_PROJECT_SUBJECT_PREFIX: str = "urn:infobim:ifcproject/"

StorageNamespaceBootstrap.initialize()

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


def _declared_subject(project_path: Path) -> Optional[URIRef]:
    """
    Return the single IfcProject the project declares, if it declares one.
    """
    dataset_path: Path = project_path / ProjectContract.DATASET_NAME
    if not dataset_path.is_dir():
        return None

    ifc_project_path: Path = _ifc_project_path(dataset_path)
    if not ifc_project_path.is_file():
        return None

    graph: Optional[Graph] = _load_graph(ifc_project_path)
    if graph is None:
        return None

    subjects: List[URIRef] = _ifc_project_subjects(graph)
    if len(subjects) != 1:
        return None

    return subjects[0]


def _is_project_ready(project_path: Path) -> bool:
    """
    Report whether the project declares one IfcProject carrying a GlobalId.
    """
    subject: Optional[URIRef] = _declared_subject(project_path)
    if subject is None:
        return False

    graph: Optional[Graph] = _load_graph(
        _ifc_project_path(project_path / ProjectContract.DATASET_NAME)
    )
    if graph is None:
        return False

    return _has_global_id(graph, subject)


def _is_schema_ready(project_path: Path) -> bool:
    """
    Report whether the project resolves to exactly one IFC schema.
    """
    subject: Optional[URIRef] = _declared_subject(project_path)
    if subject is None:
        return False

    graph: Optional[Graph] = _load_graph(
        _ifc_project_path(project_path / ProjectContract.DATASET_NAME)
    )
    if graph is None:
        return False

    return len(_schema_values(graph, subject)) == 1


def _encode_ifc64(number: int, length: int) -> str:
    characters: List[str] = ["0"] * length
    value: int = number
    for index in range(length - 1, -1, -1):
        characters[index] = _IFC64_ALPHABET[value % 64]
        value //= 64

    if value:
        raise ValueError("Value does not fit in the requested IFC base64 length.")

    return "".join(characters)


def _new_ifc_global_id() -> str:
    raw: bytes = uuid.uuid4().bytes
    compressed: str = _encode_ifc64(raw[0], 2)
    offset: int
    for offset in range(1, 16, 3):
        compressed += _encode_ifc64(
            int.from_bytes(raw[offset:offset + 3], "big"),
            4,
        )

    return compressed


def _project_name(project_path: Path) -> Optional[str]:
    metadata_path: Path = StorageBootstrap.get_container_storage_file_path(
        project_path,
    )
    if not metadata_path.is_file():
        return None

    graph: Optional[Graph] = _load_graph(metadata_path)
    if graph is None:
        return None

    subjects: List[URIRef] = [
        subject
        for subject in graph.subjects(
            RDF.type,
            StorageNamespaceBootstrap.OBDC.DataContainer,
        )
        if isinstance(subject, URIRef)
    ]
    if len(subjects) != 1:
        return None

    for title in graph.objects(subjects[0], DCTERMS.title):
        name: str = str(title).strip()
        if name:
            return name

    return None


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
    if ifc_project_path.is_file():
        graph: Optional[Graph] = _load_graph(ifc_project_path)
        if graph is None:
            return 1
    else:
        graph = Graph()

    subjects: List[URIRef] = _ifc_project_subjects(graph)
    if len(subjects) > 1:
        return 1

    if subjects:
        return 0 if _is_project_ready(resolved_project_path) else 1

    # An existing non-empty payload with no valid IfcProject is invalid.
    # The hotfix does not migrate, reinterpret or preserve legacy structures.
    if len(graph) > 0:
        return 1

    project_name: Optional[str] = _project_name(resolved_project_path)
    if project_name is None:
        return 1

    schema_uri: str = (
        schema.strip()
        if isinstance(schema, str) and schema.strip()
        else ProjectContract.DEFAULT_IFC_SCHEMA
    )
    namespace: Optional[str] = _ifcowl_namespace_from_schema(schema_uri)
    if namespace is None:
        return 1

    global_id: str = _new_ifc_global_id()
    subject: URIRef = URIRef(f"{_IFC_PROJECT_SUBJECT_PREFIX}{global_id}")
    graph.add((
        subject,
        RDF.type,
        URIRef(f"{namespace}IfcProject"),
    ))
    graph.add((
        subject,
        URIRef(f"{namespace}globalId_IfcRoot"),
        Literal(global_id),
    ))
    graph.add((
        subject,
        URIRef(f"{namespace}name_IfcRoot"),
        Literal(project_name),
    ))
    graph.bind("ifcowl", Namespace(namespace), replace=True)

    try:
        ifc_project_path.parent.mkdir(parents=True, exist_ok=True)
        ifc_project_path.write_bytes(
            graph.serialize(format="turtle", encoding="utf-8")
        )
    except OSError:
        return 1

    if not _is_project_ready(resolved_project_path):
        return 1
    if not _is_schema_ready(resolved_project_path):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
