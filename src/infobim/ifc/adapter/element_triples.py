import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Tuple

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF

from infobim.project.domain.model.contract import ProjectContract


class IfcElementTriples:
    """
    What the container says about IFC elements that the IFC model does not: the
    documents of the container they are related to and their tags.

    It is kept as RDF, not in the IFC model: in the reserved dataset of the
    project, in a Turtle file of ``payload/triple`` for each IFC class, named
    after it (``IfcWall`` in ``ifc_wall.ttl``). An element that has any of it is a
    subject of the file, typed with its class in the ifcOWL namespace of the
    schema of its model, with its GlobalId, the documents as ``dcterms:relation``
    and the tags as ``schema:keywords``. An element with none is not in the file,
    and a file with no element is removed.
    """

    #: The fields kept here, by the property of the element that holds each, and whether its values are IRIs.
    FIELDS: ClassVar[Dict[str, Tuple[Any, bool]]] = {
        "related_documents": (DCTERMS.relation, True),
        "tags": (URIRef("http://schema.org/keywords"), False),
    }
    GLOBAL_ID: ClassVar[str] = "globalId_IfcRoot"
    SUBJECT_BASE: ClassVar[str] = "urn:infobim:"
    SEPARATOR: ClassVar[str] = "|"
    ENCODING: ClassVar[str] = "utf-8"

    def __init__(self, project_path: Path) -> None:
        self._project_path: Path = project_path
        self._graphs: Dict[Path, Graph] = {}

    @classmethod
    def split(cls, text: str) -> List[str]:
        """The values a field text names: the ones it separates by a vertical bar."""
        return sorted({part.strip() for part in text.split(cls.SEPARATOR) if part.strip()})

    def file(self, ifc_class: str) -> Path:
        """The Turtle file of the class: ``IfcWall`` is ``ifc_wall.ttl``."""
        name: str = re.sub(r"(?<!^)(?=[A-Z])", "_", ifc_class).lower()
        return (
            self._project_path
            / ProjectContract.DATASET_NAME
            / ProjectContract.PAYLOAD_DIRECTORY_NAME
            / ProjectContract.TRIPLE_DIRECTORY_NAME
            / f"{name}.ttl"
        )

    @classmethod
    def subject(cls, ifc_class: str, global_id: str) -> URIRef:
        """The resource of the element, as the one of the IfcProject is: ``urn:infobim:ifcwall/<GlobalId>``."""
        return URIRef(f"{cls.SUBJECT_BASE}{ifc_class.lower()}/{global_id}")

    def read(self, ifc_class: str, global_id: str) -> Dict[str, List[str]]:
        """The values of each field the container keeps for the element, sorted."""
        graph: Graph = self._graph(self.file(ifc_class))
        subject: URIRef = self.subject(ifc_class, global_id)
        return {
            field: sorted(str(value) for value in graph.objects(subject, predicate))
            for field, (predicate, _) in self.FIELDS.items()
        }

    def write(self, namespace: str, ifc_class: str, global_id: str, values: Dict[str, List[str]]) -> None:
        """
        Make the values the ones the container keeps for the element. The ifcOWL namespace is the one of
        the schema of the model; the rest of what the file says is kept as it was.
        """
        path: Path = self.file(ifc_class)
        graph: Graph = self._graph(path)
        subject: URIRef = self.subject(ifc_class, global_id)
        ifcowl: Namespace = Namespace(namespace)
        graph.remove((subject, RDF.type, None))
        graph.remove((subject, ifcowl[self.GLOBAL_ID], None))
        for field, (predicate, iri) in self.FIELDS.items():
            if field in values:
                graph.remove((subject, predicate, None))
                for value in values[field]:
                    graph.add((subject, predicate, URIRef(value) if iri else Literal(value)))
        if any((subject, predicate, None) in graph for predicate, _ in self.FIELDS.values()):
            graph.add((subject, RDF.type, ifcowl[ifc_class]))
            graph.add((subject, ifcowl[self.GLOBAL_ID], Literal(global_id)))

        if len(graph) == 0:
            path.unlink(missing_ok=True)
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        graph.bind("ifcowl", ifcowl)
        graph.bind("dcterms", DCTERMS)
        graph.bind("schema", Namespace("http://schema.org/"), override=True, replace=True)
        path.write_text(graph.serialize(format="turtle"), encoding=self.ENCODING)

    def _graph(self, path: Path) -> Graph:
        if path not in self._graphs:
            graph: Graph = Graph()
            if path.is_file():
                graph.parse(str(path), format="turtle")
            self._graphs[path] = graph

        return self._graphs[path]
