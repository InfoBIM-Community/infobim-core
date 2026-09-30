import unicodedata
from typing import Set, Tuple
from importlib.resources.abc import Traversable

from rdflib import Graph, URIRef
from rdflib.term import Node
from rdflib.namespace import RDF, OWL, SKOS, RDFS, DCTERMS
from brasidatacenter.resources import iter_ontology_files

from infobim.context.domain.port.kind import KindResolverPort


class OntologyKindResolver(KindResolverPort):
    """Search every packaged kind ontology without a domain allow-list."""

    def resolve(self, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Kind must be a non-empty string.")
        token: str = self._normalize(value)
        if not token:
            raise ValueError("Kind must contain letters or digits.")
        identifiers: Set[str] = set()
        labels: Set[str] = set()
        found: bool = False
        resource: Traversable

        for resource in iter_ontology_files(suffixes=(".ttl",)):
            if resource.name != "kind.ttl":
                continue
            found = True
            graph: Graph = Graph()
            graph.parse(data=resource.read_text(encoding="utf-8"), format="turtle")
            direct: Set[str]
            named: Set[str]
            direct, named = self._matches(graph, value.strip(), token)
            identifiers.update(direct)
            labels.update(named)

        if not found:
            raise ValueError("No kind ontologies were found in BrasidataCenter.")

        matches: Set[str] = identifiers if identifiers else labels
        if not matches:
            raise ValueError(f"Unknown kind: {value!r}.")
        if len(matches) != 1:
            raise ValueError(
                f"Ambiguous kind {value!r}; use a concept URI: "
                + ", ".join(sorted(matches))
            )
        return next(iter(matches))

    @classmethod
    def _matches(
        cls, graph: Graph, value: str, token: str
    ) -> Tuple[Set[str], Set[str]]:
        identifiers: Set[str] = set()
        labels: Set[str] = set()
        subjects: Set[Node] = set(graph.subjects(RDF.type, OWL.Class))
        subjects.update(graph.subjects(RDF.type, RDFS.Class))
        subjects.update(graph.subjects(RDF.type, SKOS.Concept))
        subject: Node
        for subject in subjects:
            if not isinstance(subject, URIRef):
                continue
            uri: str = str(subject)
            local_name: str = uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            if value == uri or token == cls._normalize(local_name):
                identifiers.add(uri)
            predicate: URIRef
            for predicate in (DCTERMS.identifier, SKOS.prefLabel, SKOS.altLabel, RDFS.label):
                term: Node
                for term in graph.objects(subject, predicate):
                    if cls._normalize(str(term)) == token:
                        if predicate == DCTERMS.identifier:
                            identifiers.add(uri)
                        else:
                            labels.add(uri)
        return identifiers, labels

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed: str = unicodedata.normalize("NFKD", value)
        character: str
        return "".join(
            character for character in decomposed
            if character.isalnum() and not unicodedata.combining(character)
        ).casefold()
