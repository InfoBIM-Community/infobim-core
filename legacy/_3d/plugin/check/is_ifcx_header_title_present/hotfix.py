import json
from pathlib import Path
from typing import Any, Dict, Optional

from rdflib import Graph, URIRef

from infobim.project.domain.model.contract import ProjectContract
from infobim.drawing.domain.exception.repair import IfcxTitleUnrecoverableError

# Standalone hotfix. It imports no sibling check/hotfix.
#
# An IFCX file's title is not recovered here. is_drawing_linked_to_project
# is what fills a drawing's name_IfcRoot into the drawing's own
# linkset -- the DXF document's own ct:filename, stem only, already on
# that same linkset. This hotfix only copies that value into the IFCX
# header, and keeps it synced: a title that already matches is left
# alone, one that differs is overwritten, since the linkset is the
# single source of truth once it has an answer. Only when the linkset
# has none (no linkset at all, or no name_IfcRoot on it yet) does an
# existing title survive as-is, and only then does a header with no
# title at all raise, rather than re-deriving one a second, possibly
# divergent way.

CONTAINER_NAMESPACE: str = "https://standards.iso.org/iso/21597/-1/ed-1/en/Container#"
DOCUMENT_URI_PREFIX: str = "urn:infobim:document/"
IFCOWL_NAMESPACE_BASE: str = "https://standards.buildingsmart.org/IFC/DEV/"
NAME_LOCAL_NAME: str = "name_IfcRoot"
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


def _has_title(document: Dict[str, Any]) -> bool:
    header: Any = document.get("header")
    return (
        isinstance(header, dict)
        and isinstance(header.get("title"), str)
        and bool(header["title"].strip())
    )


def _linkset_path(container_path: Path, dxf_hash: str) -> Path:
    return (
        container_path
        / ProjectContract.DATASET_NAME
        / ProjectContract.PAYLOAD_DIRECTORY_NAME
        / LINKSET_DIRECTORY_NAME
        / f"{dxf_hash}.ttl"
    )


def _title_from_linkset(container_path: Path, dxf_hash: str) -> Optional[str]:
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
            and str(predicate).endswith(f"#{NAME_LOCAL_NAME}")
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

    title: Optional[str] = _title_from_linkset(
        resolved_container_path, resolved_ifcx_path.stem
    )
    if title is None:
        # No linkset (or no name_IfcRoot on it) to sync against -- a
        # title already there is left alone rather than blocked on a
        # source this drawing may never have had. Nothing there at all
        # is unrecoverable: nothing else in this codebase names a
        # drawing.
        if _has_title(document):
            return 0
        raise IfcxTitleUnrecoverableError(
            f"The drawing linkset for {resolved_ifcx_path} carries no "
            f"name_IfcRoot yet, so its title cannot be recovered. Run "
            f"is_drawing_linked_to_project's hotfix on that linkset first."
        )

    header: Any = document.get("header")
    if not isinstance(header, dict):
        return 1

    if header.get("title") == title:
        return 0

    header["title"] = title
    resolved_ifcx_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    verified: Optional[Dict[str, Any]] = _document(resolved_ifcx_path)
    verified_header: Any = verified.get("header") if isinstance(verified, dict) else None
    return 0 if isinstance(verified_header, dict) and verified_header.get("title") == title else 1


if __name__ == "__main__":
    raise SystemExit(main())
