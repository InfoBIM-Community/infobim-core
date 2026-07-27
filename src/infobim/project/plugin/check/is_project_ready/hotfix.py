from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF, Namespace

from ontobdc.storage.adapter.bootstrap import (
    ensure_ontobdc_directory,
    get_container_storage_file_path,
)

_INFOBIM_MARKER_DIR_NAME: str = "__infobim__"
_PROJECT_TTL_FILE_NAME: str = "project.ttl"

_IFCOWL: Namespace = Namespace("http://ifcowl.openbimstandards.org/IFC4#")
_BOT: Namespace = Namespace("https://w3id.org/bot#")
_DICE: Namespace = Namespace("https://w3id.org/digitalconstruction/0.5/Entities#")
_PROV: Namespace = Namespace("http://www.w3.org/ns/prov#")


def _resolve_container_path(container_path: Optional[str]) -> Optional[Path]:
    if not isinstance(container_path, str) or not container_path.strip():
        return None
    return Path(container_path).expanduser().resolve()


def _extract_container_subject(container_ttl: Path) -> Optional[URIRef]:
    container_graph: Graph = Graph()
    try:
        container_graph.parse(str(container_ttl), format="turtle")
    except Exception:
        return None

    subjects = [subject for subject in container_graph.subjects() if isinstance(subject, URIRef)]
    if len(subjects) == 1:
        return subjects[0]

    identifier_subjects = [
        subject
        for subject in container_graph.subjects(DCTERMS.identifier, None)
        if isinstance(subject, URIRef)
    ]
    if len(identifier_subjects) == 1:
        return identifier_subjects[0]

    return None


def main(container_path: Optional[str] = None) -> int:
    try:
        resolved_container_path: Optional[Path] = _resolve_container_path(container_path)
        if resolved_container_path is None:
            return 1

        resolved_container_path.mkdir(parents=True, exist_ok=True)
        marker_dir: Path = ensure_ontobdc_directory(resolved_container_path)

        container_ttl: Path = get_container_storage_file_path(resolved_container_path)
        container_subject: Optional[URIRef] = None
        if container_ttl.is_file():
            container_subject = _extract_container_subject(container_ttl)

        infobim_marker_dir: Path = marker_dir / _INFOBIM_MARKER_DIR_NAME
        infobim_marker_dir.mkdir(parents=True, exist_ok=True)
        project_file: Path = infobim_marker_dir / _PROJECT_TTL_FILE_NAME

        project_graph: Graph = Graph()
        project_graph.bind("rdf", RDF)
        project_graph.bind("dcterms", DCTERMS)
        project_graph.bind("prov", _PROV)
        project_graph.bind("ifcowl", _IFCOWL)
        project_graph.bind("bot", _BOT)
        project_graph.bind("dice", _DICE)

        container_uri: URIRef = URIRef(resolved_container_path.as_uri())
        project_ref: URIRef = URIRef(f"urn:infobim:project:{resolved_container_path.name or 'local'}")
        #building_ref: URIRef = URIRef(f"{project_ref}:building")

        project_graph.add((project_ref, RDF.type, _IFCOWL.IfcProject))
        project_graph.add((project_ref, _PROV.atLocation, container_uri))
        if container_subject is not None:
            project_graph.add((project_ref, DCTERMS.isPartOf, container_subject))

        #project_graph.add((building_ref, RDF.type, _BOT.Building))
        #project_graph.add((building_ref, RDF.type, _DICE.Building))
        #project_graph.add((building_ref, _PROV.atLocation, container_uri))
        #project_graph.add((project_ref, DCTERMS.hasPart, building_ref))

        serialized_graph: bytes = project_graph.serialize(format="turtle", encoding="utf-8")
        project_file.write_bytes(serialized_graph)
        return 0
    except Exception:
        return 1
