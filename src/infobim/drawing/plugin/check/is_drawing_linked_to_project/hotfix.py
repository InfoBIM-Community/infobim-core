from pathlib import Path
from typing import List, Optional, Tuple

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS

from ontobdc.storage.adapter.crate import ContainerRoCrate

from infobim.project.domain.model.contract import ProjectContract
from infobim.drawing.adapter.transformation_payload import TransformationPayloadPath
from infobim.drawing.domain.exception.repair import DrawingDwgLinkUnrecoverableError

# Standalone hotfix. It imports no sibling check/hotfix.
#
# A DXF/IFCX linkset never records the DWG a DXF was itself converted
# from (see DxfIfcxLinksetWriter) -- that is a separate linkset,
# DwgDxfLinksetWriter's, written only while the DWG-to-DXF conversion
# still has both files to write it from. That linkset is NOT assumed to
# exist here: recovering the link instead means finding, by content
# hash rather than by name, the actual DWG file the cached DXF this
# document identifies was converted from -- first among every DWG the
# Project's own tree holds, then among every DWG its RO-Crate lists
# (the same two-tier search is_ifcx_header_title_present used to use to
# recover a title, now applied one hash-chain step further up: from the
# cached DXF's hash-named cache location to the real DWG bytes it
# names). Neither lookup guesses from a partial match -- a hash either
# matches exactly or it does not, and when none does, the source DWG
# truly is not recoverable, so this raises rather than inventing a name
# or leaving the link out.
#
# globalId_IfcRoot is a fresh IFC GlobalId (ifcopenshell.guid.new(), the
# standard 22-character compressed form) generated once per DXF document
# and then left alone -- it identifies this document, not anything it
# was derived from, so there is no "correct" value to recover it from.
# name_IfcRoot is the DXF document's own ct:filename, stem only -- the
# linkset already carries it, so this never depends on the DWG link.

CONTAINER_NAMESPACE: str = "https://standards.iso.org/iso/21597/-1/ed-1/en/Container#"
IFCOWL_NAMESPACE_BASE: str = "https://standards.buildingsmart.org/IFC/DEV/"
IFCOWL_PREFIX: str = "ifc4x3"
DOCUMENT_URI_PREFIX: str = "urn:infobim:document/"
DOCUMENT_INFORMATION_LOCAL_NAME: str = "IfcDocumentInformation"
GLOBAL_ID_LOCAL_NAME: str = "globalId_IfcRoot"
NAME_LOCAL_NAME: str = "name_IfcRoot"
GLOBAL_ID_LENGTH: int = 22
DWG_FORMAT: str = "dwg"
DXF_FORMAT: str = "dxf"
DWG_SUFFIX: str = ".dwg"
DXF_SUFFIX: str = ".dxf"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _container_path_of(linkset_path: Path) -> Optional[Path]:
    for ancestor in linkset_path.parents:
        if ancestor.name == ProjectContract.DATASET_NAME:
            return ancestor.parent
    return None


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


def _identifier_of(graph: Graph, subject: URIRef) -> Optional[str]:
    value: object
    for value in graph.objects(subject, URIRef(f"{CONTAINER_NAMESPACE}hasIdentifier")):
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


def _dwg_target_of(graph: Graph, dxf_document: URIRef) -> Optional[Tuple[URIRef, str]]:
    target: object
    for target in graph.objects(dxf_document, DCTERMS.isVersionOf):
        if not isinstance(target, URIRef) or not _is_external_document(graph, target):
            continue
        filename: Optional[str] = _filename_of(graph, target)
        if filename is not None and filename.lower().endswith(DWG_SUFFIX):
            return target, filename
    return None


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


def _dwg_hash_of(
    container_path: Path, filename: str, content_identifier: str
) -> Optional[str]:
    """
    Return the source DWG's content hash, read off the cache directory
    (or hash-named file) the matching cached DXF sits under.
    """
    cache_dir: Path = TransformationPayloadPath.directory_for(
        container_path, DWG_FORMAT, DXF_FORMAT
    )
    if not cache_dir.is_dir():
        return None

    candidate: Path
    for candidate in cache_dir.rglob(filename):
        if not candidate.is_file():
            continue
        if TransformationPayloadPath.identifier_for(candidate) != content_identifier:
            continue
        if candidate.parent == cache_dir:
            return candidate.stem
        return candidate.parent.name

    return None


def _dwg_path_from_project_tree(project_path: Path, dwg_hash: str) -> Optional[Path]:
    candidate: Path
    for candidate in project_path.rglob(f"*{DWG_SUFFIX}"):
        if not candidate.is_file():
            continue
        if TransformationPayloadPath.identifier_for(candidate) == dwg_hash:
            return candidate
    return None


def _dwg_path_from_ro_crate(project_path: Path, dwg_hash: str) -> Optional[Path]:
    try:
        file_paths: List[str] = ContainerRoCrate.file_paths(project_path)
    except ValueError:
        return None

    relative_path: str
    for relative_path in file_paths:
        if not relative_path.lower().endswith(DWG_SUFFIX):
            continue

        candidate: Path = project_path / relative_path
        if not candidate.is_file():
            continue
        if TransformationPayloadPath.identifier_for(candidate) == dwg_hash:
            return candidate

    return None


def _dwg_document_of(
    project_path: Path, dwg_hash: str
) -> Optional[Tuple[URIRef, str]]:
    """
    Return the source DWG's own document URI and filename, found by
    hashing real DWG files -- first every DWG the Project's own tree
    holds, then every DWG its RO-Crate lists -- rather than trusting a
    dwg-dxf linkset that may never have been written.
    """
    dwg_path: Optional[Path] = _dwg_path_from_project_tree(
        project_path, dwg_hash
    ) or _dwg_path_from_ro_crate(project_path, dwg_hash)
    if dwg_path is None:
        return None

    return URIRef(f"{DOCUMENT_URI_PREFIX}dwg/{dwg_hash}"), dwg_path.name


def main(linkset_path: str = None, container_path: str = None) -> int:
    resolved_linkset_path: Optional[Path] = _resolve_path(linkset_path)
    if resolved_linkset_path is None or not resolved_linkset_path.is_file():
        return 1

    resolved_container_path: Optional[Path] = _resolve_path(
        container_path
    ) or _container_path_of(resolved_linkset_path)
    if resolved_container_path is None:
        return 1

    graph: Optional[Graph] = _load_graph(resolved_linkset_path)
    if graph is None:
        return 1

    graph.bind(IFCOWL_PREFIX, Namespace(ProjectContract.IFCOWL_NAMESPACE))

    dxf_documents: List[URIRef] = _dxf_documents(graph)
    if not dxf_documents:
        return 1

    changed: bool = False
    dxf_document: URIRef
    for dxf_document in dxf_documents:
        if _dwg_target_of(graph, dxf_document) is None:
            filename: Optional[str] = _filename_of(graph, dxf_document)
            identifier: Optional[str] = _identifier_of(graph, dxf_document)
            if filename is None or identifier is None:
                raise DrawingDwgLinkUnrecoverableError(
                    f"The DXF document at {resolved_linkset_path} carries "
                    f"no filename/identifier to locate its source DWG by."
                )

            dwg_hash: Optional[str] = _dwg_hash_of(
                resolved_container_path, filename, identifier
            )
            if dwg_hash is None:
                raise DrawingDwgLinkUnrecoverableError(
                    f"No cached DWG-to-DXF conversion under "
                    f"{resolved_container_path} matches {filename}'s "
                    f"content, so its source DWG cannot be located."
                )

            dwg_document_and_filename: Optional[Tuple[URIRef, str]] = _dwg_document_of(
                resolved_container_path, dwg_hash
            )
            if dwg_document_and_filename is None:
                raise DrawingDwgLinkUnrecoverableError(
                    f"No DWG file under {resolved_container_path} (nor its "
                    f"RO-Crate) hashes to {dwg_hash!r}, so the source DWG "
                    f"{filename} was converted from is not recoverable."
                )

            dwg_document, dwg_filename = dwg_document_and_filename
            graph.add((dxf_document, DCTERMS.isVersionOf, dwg_document))
            graph.add((dwg_document, DCTERMS.hasVersion, dxf_document))
            graph.add(
                (dwg_document, RDF.type, URIRef(f"{CONTAINER_NAMESPACE}ExternalDocument"))
            )
            graph.add(
                (dwg_document, URIRef(f"{CONTAINER_NAMESPACE}filename"), Literal(dwg_filename))
            )
            graph.add(
                (dwg_document, URIRef(f"{CONTAINER_NAMESPACE}hasIdentifier"), Literal(dwg_hash))
            )
            changed = True

        if not _is_document_information(graph, dxf_document):
            graph.add(
                (
                    dxf_document,
                    RDF.type,
                    URIRef(f"{ProjectContract.IFCOWL_NAMESPACE}{DOCUMENT_INFORMATION_LOCAL_NAME}"),
                )
            )
            changed = True

        if _property_value(graph, dxf_document, GLOBAL_ID_LOCAL_NAME) is None:
            import ifcopenshell.guid

            graph.add(
                (
                    dxf_document,
                    URIRef(f"{ProjectContract.IFCOWL_NAMESPACE}{GLOBAL_ID_LOCAL_NAME}"),
                    Literal(ifcopenshell.guid.new()),
                )
            )
            changed = True

        if _property_value(graph, dxf_document, NAME_LOCAL_NAME) is None:
            dxf_filename: Optional[str] = _filename_of(graph, dxf_document)
            if dxf_filename is None:
                raise DrawingDwgLinkUnrecoverableError(
                    f"The DXF document at {resolved_linkset_path} carries "
                    f"no ct:filename to name it after."
                )

            graph.add(
                (
                    dxf_document,
                    URIRef(f"{ProjectContract.IFCOWL_NAMESPACE}{NAME_LOCAL_NAME}"),
                    Literal(Path(dxf_filename).stem),
                )
            )
            changed = True

    if changed:
        resolved_linkset_path.write_bytes(graph.serialize(format="turtle", encoding="utf-8"))

    verified: Optional[Graph] = _load_graph(resolved_linkset_path)
    if verified is None:
        return 1

    for dxf_document in _dxf_documents(verified):
        if _dwg_target_of(verified, dxf_document) is None:
            return 1
        if not _is_document_information(verified, dxf_document):
            return 1

        global_id: Optional[str] = _property_value(
            verified, dxf_document, GLOBAL_ID_LOCAL_NAME
        )
        if not isinstance(global_id, str) or len(global_id) != GLOBAL_ID_LENGTH:
            return 1

        name: Optional[str] = _property_value(verified, dxf_document, NAME_LOCAL_NAME)
        if not isinstance(name, str) or not name.strip():
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
