from pathlib import Path
from typing import Any, Optional

import json

from rdflib import Graph, URIRef

from infobim.project.domain.model.contract import ProjectContract

# Standalone health check. It imports no sibling check/hotfix and performs
# no mutation. An IFCX file is healthy for this concern only when its
# header's "infobim::globalId" matches the drawing's own linkset --
# globalId_IfcRoot, the fresh IFC GlobalId is_drawing_linked_to_project
# generates once per drawing -- not just when some GlobalId happens to
# be present: a GlobalId that no longer matches the linkset's own is
# stale, not healthy.

DOCUMENT_URI_PREFIX: str = "urn:infobim:document/"
IFCOWL_NAMESPACE_BASE: str = "https://standards.buildingsmart.org/IFC/DEV/"
GLOBAL_ID_LOCAL_NAME: str = "globalId_IfcRoot"
GLOBAL_ID_HEADER_KEY: str = "infobim::globalId"
LINKSET_DIRECTORY_NAME: str = "linkset"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    return Path(path_value).expanduser().resolve()


def _container_path_of(ifcx_path: Path) -> Optional[Path]:
    for ancestor in ifcx_path.parents:
        if ancestor.name == ProjectContract.DATASET_NAME:
            return ancestor.parent
    return None


def _document(ifcx_path: Path) -> Optional[Any]:
    try:
        return json.loads(ifcx_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _global_id_of(document: Any) -> Optional[str]:
    header: Any = document.get("header") if isinstance(document, dict) else None
    global_id: Any = header.get(GLOBAL_ID_HEADER_KEY) if isinstance(header, dict) else None
    return global_id if isinstance(global_id, str) and global_id.strip() else None


def _global_id_from_linkset(container_path: Path, dxf_hash: str) -> Optional[str]:
    linkset_path: Path = (
        container_path
        / ProjectContract.DATASET_NAME
        / ProjectContract.PAYLOAD_DIRECTORY_NAME
        / LINKSET_DIRECTORY_NAME
        / f"{dxf_hash}.ttl"
    )
    if not linkset_path.is_file():
        return None

    graph: Graph = Graph()
    try:
        graph.parse(str(linkset_path), format="turtle")
    except Exception:
        return None

    dxf_document: URIRef = URIRef(f"{DOCUMENT_URI_PREFIX}dxf/{dxf_hash}")
    predicate: URIRef
    value: object
    for predicate, value in graph.predicate_objects(dxf_document):
        if (
            isinstance(predicate, URIRef)
            and str(predicate).startswith(IFCOWL_NAMESPACE_BASE)
            and str(predicate).endswith(f"#{GLOBAL_ID_LOCAL_NAME}")
        ):
            text: str = str(value)
            return text if text.strip() else None

    return None


def main(ifcx_path: str = None, container_path: str = None) -> int:
    """
    Return 0 if the IFCX header's infobim::globalId matches the
    drawing's own linkset globalId_IfcRoot, 1 if it is missing or
    differs, 2 if the file cannot even be read as an IFCX document, or
    its linkset does not exist to compare against.
    """
    resolved_path: Optional[Path] = _resolve_path(ifcx_path)
    if resolved_path is None or not resolved_path.is_file():
        return 2

    document: Any = _document(resolved_path)
    if not isinstance(document, dict):
        return 2

    resolved_container_path: Optional[Path] = _resolve_path(
        container_path
    ) or _container_path_of(resolved_path)
    if resolved_container_path is None:
        return 2

    expected_global_id: Optional[str] = _global_id_from_linkset(
        resolved_container_path, resolved_path.stem
    )
    if expected_global_id is None:
        return 2

    return 0 if _global_id_of(document) == expected_global_id else 1


if __name__ == "__main__":
    raise SystemExit(main())
