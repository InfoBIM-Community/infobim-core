from pathlib import Path
from typing import List, Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, Namespace

_ONTOBDC_MARKER_DIR_NAME: str = ".__ontobdc__"
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


def _project_file_path(container_path: Path) -> Path:
    return container_path / _ONTOBDC_MARKER_DIR_NAME / _INFOBIM_MARKER_DIR_NAME / _PROJECT_TTL_FILE_NAME


def _has_project_location(project_graph: Graph, container_uri: str) -> bool:
    subjects: List[URIRef] = [
        subject
        for subject in project_graph.subjects(RDF.type, _IFCOWL.IfcProject)
        if isinstance(subject, URIRef)
    ]
    if not subjects:
        return False

    subject: URIRef
    for subject in subjects:
        locations: List[str] = [
            str(location).strip()
            for location in project_graph.objects(subject, _PROV.atLocation)
            if str(location).strip()
        ]
        if container_uri in locations:
            return True

    return False


def _has_topology_entities(project_graph: Graph) -> bool:
    bot_buildings: List[URIRef] = [
        subject
        for subject in project_graph.subjects(RDF.type, _BOT.Building)
        if isinstance(subject, URIRef)
    ]
    dice_buildings: List[URIRef] = [
        subject
        for subject in project_graph.subjects(RDF.type, _DICE.Building)
        if isinstance(subject, URIRef)
    ]
    return bool(bot_buildings or dice_buildings)


def main(container_path: Optional[str] = None) -> int:
    try:
        resolved_container_path: Optional[Path] = _resolve_container_path(container_path)
        if resolved_container_path is None or not resolved_container_path.is_dir():
            return 1

        project_file: Path = _project_file_path(resolved_container_path)
        if not project_file.is_file():
            return 1

        project_graph: Graph = Graph()
        project_graph.parse(str(project_file), format="turtle")

        container_uri: str = URIRef(resolved_container_path.as_uri()).toPython()
        if not _has_project_location(project_graph, container_uri):
            return 1

        #if not _has_topology_entities(project_graph):
        #    return 1

        return 0
    except Exception:
        return 1
