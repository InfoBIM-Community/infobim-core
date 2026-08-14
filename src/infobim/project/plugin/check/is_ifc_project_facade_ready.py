from pathlib import Path
from typing import Optional

from infobim.project.domain.model.contract import IFC_PROJECT_CLASS_URI, IFC_PROJECT_FACADE_URI, IFC_PROJECT_FIELDS, PROJECT_DATASET_NAME
from ontobdc.storage.adapter.bootstrap import get_ontobdc_directory
from rdflib import Graph, URIRef


def facade_path(container_path: str) -> Path:
    dataset_path = Path(container_path).expanduser().resolve() / PROJECT_DATASET_NAME
    return get_ontobdc_directory(dataset_path) / "linkset" / "facade.ttl"


def evaluate(*, container_path: str) -> bool:
    path = facade_path(container_path)
    if not path.is_file():
        return False
    graph = Graph()
    try:
        graph.parse(str(path), format="turtle")
    except Exception:
        return False

    entity = URIRef(IFC_PROJECT_CLASS_URI)
    facade = URIRef(IFC_PROJECT_FACADE_URI)
    has_facade = any(str(predicate).endswith("hasDataEntityFacade") for _, predicate, _ in graph.triples((entity, None, facade)))
    if not has_facade:
        return False

    fields = [obj for _, predicate, obj in graph.triples((facade, None, None)) if str(predicate).endswith("hasFacadeField")]
    return len(fields) == len(IFC_PROJECT_FIELDS)


def main(container_path: Optional[str] = None) -> int:
    if not container_path:
        return 1
    return 0 if evaluate(container_path=container_path) else 1
