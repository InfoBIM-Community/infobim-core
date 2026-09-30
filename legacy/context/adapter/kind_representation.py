import json
from typing import Any, Dict, List, Set
from importlib.resources.abc import Traversable

from rdflib import BNode, Graph, URIRef, Namespace
from rdflib.term import Node
from rdflib.namespace import OWL, RDF, RDFS
from brasidatacenter.resources import iter_ontology_files

from infobim.context.domain.port.kind_representation import KindRepresentationResolverPort


class OntologyKindRepresentationResolver(KindRepresentationResolverPort):
    def resolve(self, kind: str) -> str:
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("element_kind is required to resolve its representation.")
        graph: Graph = self._ontology_graph()
        kind_uri: URIRef = URIRef(kind)
        crm: Namespace = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
        candidates: Set[str] = set()
        restriction: Node
        for restriction in graph.objects(kind_uri, RDFS.subClassOf):
            if (restriction, RDF.type, OWL.Restriction) not in graph:
                continue
            if (restriction, OWL.onProperty, crm.P138i_has_representation) in graph:
                representation: Node
                for representation in graph.objects(restriction, OWL.someValuesFrom):
                    if not isinstance(representation, URIRef):
                        raise ValueError("The kind representation must be a named URI.")
                    candidates.add(str(representation))
        for restriction in graph.subjects(OWL.someValuesFrom, kind_uri):
            if (restriction, RDF.type, OWL.Restriction) not in graph:
                continue
            if (restriction, OWL.onProperty, crm.P138_represents) in graph:
                for representation in graph.subjects(RDFS.subClassOf, restriction):
                    if not isinstance(representation, URIRef):
                        raise ValueError("The kind representation must be a named URI.")
                    candidates.add(str(representation))
        if not candidates:
            raise ValueError(f"No representation is declared for element_kind {kind!r}.")
        if len(candidates) != 1:
            raise ValueError(
                f"Multiple representations are declared for element_kind {kind!r}: "
                + ", ".join(sorted(candidates))
            )
        return next(iter(candidates))

    def describe(self, representation: str) -> List[Dict[str, Any]]:
        if not isinstance(representation, str) or not representation.strip():
            raise ValueError("A representation URI is required to describe it.")
        graph: Graph = self._ontology_graph()
        description: Graph = self._concise_bounded_description(
            graph, URIRef(representation)
        )
        if len(description) == 0:
            raise ValueError(
                f"No ontology definition is declared for representation {representation!r}."
            )
        nodes: Any = json.loads(description.serialize(format="json-ld"))
        if not isinstance(nodes, list):
            raise ValueError("The representation JSON-LD must be an array of nodes.")
        node: Any
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("Each representation JSON-LD node must be an object.")
        return nodes

    @staticmethod
    def _ontology_graph() -> Graph:
        graph: Graph = Graph()
        resource: Traversable
        for resource in iter_ontology_files(suffixes=(".ttl",)):
            if resource.name in ("kind.ttl", "kind_representation.ttl"):
                graph.parse(data=resource.read_text(encoding="utf-8"), format="turtle")
        return graph

    @staticmethod
    def _concise_bounded_description(graph: Graph, subject: URIRef) -> Graph:
        """Copy every triple describing ``subject``, following blank nodes it owns."""
        description: Graph = Graph()
        visited: Set[Node] = set()
        frontier: List[Node] = [subject]
        node: Node
        while frontier:
            node = frontier.pop()
            if node in visited:
                continue
            visited.add(node)
            predicate: Node
            object_: Node
            for predicate, object_ in graph.predicate_objects(node):
                description.add((node, predicate, object_))
                if isinstance(object_, BNode) and object_ not in visited:
                    frontier.append(object_)
        return description
