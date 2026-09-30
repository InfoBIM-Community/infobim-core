import json
from pathlib import Path
from typing import Any, Dict, Optional

from rdflib import Graph, URIRef

from infobim.project.domain.model.contract import ProjectContract
from infobim.drawing.domain.exception.repair import IfcxGlobalIdUnrecoverableError

# Standalone hotfix. It imports no sibling check/hotfix.
#
# An IFCX file's GlobalId is not generated here. is_drawing_linked_to_project
# is what generates a drawing's own globalId_IfcRoot -- a fresh IFC GUID
# -- into the drawing's own linkset, once, the first time that concern
# is repaired. This hotfix only copies that value into the IFCX header,
# and keeps it synced: a GlobalId that already matches is left alone,
# one that differs is overwritten, since the linkset is the single
# source of truth once it has an answer -- never generating a second,
# different GlobalId for the same drawing itself. Only when the
# linkset has none yet does an existing GlobalId survive as-is, and
# only then does a header with none at all raise, rather than
# inventing one.

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


def _document(ifcx_path: Path) -> Optional[Dict[str, Any]]:
    try:
        document: Any = json.loads(ifcx_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _has_global_id(document: Dict[str, Any]) -> bool:
    header: Any = document.get("header")
    return (
        isinstance(header, dict)
        and isinstance(header.get(GLOBAL_ID_HEADER_KEY), str)
        and bool(header[GLOBAL_ID_HEADER_KEY].strip())
    )


def _linkset_path(container_path: Path, dxf_hash: str) -> Path:
    return (
        container_path
        / ProjectContract.DATASET_NAME
        / ProjectContract.PAYLOAD_DIRECTORY_NAME
        / LINKSET_DIRECTORY_NAME
        / f"{dxf_hash}.ttl"
    )


def _global_id_from_linkset(container_path: Path, dxf_hash: str) -> Optional[str]:
    linkset_path: Path = _linkset_path(container_path, dxf_hash)
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
    resolved_ifcx_path: Optional[Path] = _resolve_path(ifcx_path)
    if resolved_ifcx_path is None or not resolved_ifcx_path.is_file():
        return 1

    resolved_container_path: Optional[Path] = _resolve_path(
        container_path
    ) or _container_path_of(resolved_ifcx_path)
    if resolved_container_path is None:
        return 1

    document: Optional[Dict[str, Any]] = _document(resolved_ifcx_path)
    if document is None:
        return 1

    global_id: Optional[str] = _global_id_from_linkset(
        resolved_container_path, resolved_ifcx_path.stem
    )
    if global_id is None:
        # No linkset (or no globalId_IfcRoot on it) to sync against -- a
        # GlobalId already there is left alone rather than blocked on a
        # source this drawing may never have had.
        if _has_global_id(document):
            return 0
        raise IfcxGlobalIdUnrecoverableError(
            f"The drawing linkset for {resolved_ifcx_path} carries no "
            f"globalId_IfcRoot yet, so its infobim::globalId cannot be "
            f"recovered. Run is_drawing_linked_to_project's hotfix on "
            f"that linkset first."
        )

    header: Any = document.get("header")
    if not isinstance(header, dict):
        return 1

    if header.get(GLOBAL_ID_HEADER_KEY) == global_id:
        return 0

    header[GLOBAL_ID_HEADER_KEY] = global_id
    resolved_ifcx_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    verified: Optional[Dict[str, Any]] = _document(resolved_ifcx_path)
    verified_header: Any = verified.get("header") if isinstance(verified, dict) else None
    return (
        0
        if isinstance(verified_header, dict)
        and verified_header.get(GLOBAL_ID_HEADER_KEY) == global_id
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
