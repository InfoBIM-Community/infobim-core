from pathlib import Path
from typing import List, Optional

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import DCTERMS

# Standalone health check. It imports no sibling check/hotfix and performs
# no mutation. A drawing's DXF/IFCX linkset is healthy for this concern
# only when each DXF document it declares: points back (dcterms:isVersionOf)
# to the DWG document it was converted from, carries a globalId_IfcRoot
# and a name_IfcRoot, and is itself modeled as an ifcOWL
# IfcDocumentInformation -- not just a bare ISO 21597 ct:ExternalDocument.

IFCOWL_NAMESPACE_BASE: str = "https://standards.buildingsmart.org/IFC/DEV/"
CONTAINER_NAMESPACE: str = "https://standards.iso.org/iso/21597/-1/ed-1/en/Container#"
DOCUMENT_INFORMATION_LOCAL_NAME: str = "IfcDocumentInformation"
GLOBAL_ID_LOCAL_NAME: str = "globalId_IfcRoot"
NAME_LOCAL_NAME: str = "name_IfcRoot"
GLOBAL_ID_LENGTH: int = 22
DWG_SUFFIX: str = ".dwg"
DXF_SUFFIX: str = ".dxf"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _load_graph(path: Path) -> Optional[Graph]:
    if not path.is_file():
        return None
    graph: Graph = Graph()
    try:
        graph.parse(str(path), format="turtle")
    except Exception:
        return None
    return graph


def _is_external_document(graph: Graph, subject: URIRef) -> bool:
    return (subject, RDF.type, URIRef(f"{CONTAINER_NAMESPACE}ExternalDocument")) in graph


def _filename_of(graph: Graph, subject: URIRef) -> Optional[str]:
    value: object
    for value in graph.objects(subject, URIRef(f"{CONTAINER_NAMESPACE}filename")):
        return str(value)
    return None


def _dxf_documents(graph: Graph) -> List[URIRef]:
    documents: List[URIRef] = []
    subject: URIRef
    for subject in {s for s, _, _ in graph.triples((None, RDF.type, None))}:
        if not isinstance(subject, URIRef) or not _is_external_document(graph, subject):
            continue
        filename: Optional[str] = _filename_of(graph, subject)
        if filename is not None and filename.lower().endswith(DXF_SUFFIX):
            documents.append(subject)
    return documents


def _points_to_dwg(graph: Graph, dxf_document: URIRef) -> bool:
    target: object
    for target in graph.objects(dxf_document, DCTERMS.isVersionOf):
        if not isinstance(target, URIRef) or not _is_external_document(graph, target):
            continue
        filename: Optional[str] = _filename_of(graph, target)
        if filename is not None and filename.lower().endswith(DWG_SUFFIX):
            return True
    return False


def _property_value(graph: Graph, subject: URIRef, local_name: str) -> Optional[str]:
    predicate: URIRef
    value: object
    for predicate, value in graph.predicate_objects(subject):
        if (
            isinstance(predicate, URIRef)
            and str(predicate).startswith(IFCOWL_NAMESPACE_BASE)
            and str(predicate).endswith(f"#{local_name}")
        ):
            return str(value)
    return None


def _is_document_information(graph: Graph, subject: URIRef) -> bool:
    value: object
    for value in graph.objects(subject, RDF.type):
        if (
            isinstance(value, URIRef)
            and str(value).startswith(IFCOWL_NAMESPACE_BASE)
            and str(value).endswith(f"#{DOCUMENT_INFORMATION_LOCAL_NAME}")
        ):
            return True
    return False


def main(linkset_path: str = None) -> int:
    """
    Return 0 if every DXF document the linkset declares points to its
    source DWG, carries a globalId_IfcRoot and a name_IfcRoot, and is
    modeled as an ifcOWL IfcDocumentInformation; 1 if any of that is
    missing; 2 if the file cannot even be read as a linkset, or carries
    no DXF document at all.
    """
    resolved_path: Optional[Path] = _resolve_path(linkset_path)
    if resolved_path is None:
        return 2

    graph: Optional[Graph] = _load_graph(resolved_path)
    if graph is None:
        return 2

    dxf_documents: List[URIRef] = _dxf_documents(graph)
    if not dxf_documents:
        return 2

    dxf_document: URIRef
    for dxf_document in dxf_documents:
        if not _points_to_dwg(graph, dxf_document):
            return 1
        if not _is_document_information(graph, dxf_document):
            return 1

        global_id: Optional[str] = _property_value(
            graph, dxf_document, GLOBAL_ID_LOCAL_NAME
        )
        if not isinstance(global_id, str) or len(global_id) != GLOBAL_ID_LENGTH:
            return 1

        name: Optional[str] = _property_value(graph, dxf_document, NAME_LOCAL_NAME)
        if not isinstance(name, str) or not name.strip():
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
