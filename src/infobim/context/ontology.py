

from dataclasses import dataclass
from importlib.resources import files
from typing import List, Optional

from rdflib import Graph, Literal, URIRef


@dataclass(frozen=True)
class FacadeFieldContract:
    name: str
    datatype: str = "string"
    order: int = 0
    identifier: bool = False


@dataclass(frozen=True)
class EntityFacadeContract:
    entity_uri: str
    entity_name: str
    facade_uri: str
    fields: tuple[FacadeFieldContract, ...]


@dataclass(frozen=True)
class EntityContextContract:
    root: EntityFacadeContract
    related: tuple[EntityFacadeContract, ...]

    @property
    def entities(self) -> tuple[EntityFacadeContract, ...]:
        return (self.root, *self.related)


class InfoBIMOntologyAdapter:
    """Resolve representation-neutral entity context from bundled RDF."""

    def resolve_entity_context(self, entity: str) -> EntityContextContract:
        ns_graph = self._graph("ns.ttl")
        view_graph = self._graph("view.ttl")
        root_uri = self._resolve_entity_uri(entity, ns_graph, view_graph)
        root_facade = self._resolve_facade(root_uri, view_graph)

        related_uris: List[URIRef] = []
        for _, predicate, related in ns_graph.triples((root_uri, None, None)):
            if self._local_name(predicate) != "assignsRelatedClass":
                continue
            if isinstance(related, URIRef) and related not in related_uris:
                related_uris.append(related)

        related_facades = tuple(
            self._resolve_facade(uri, view_graph)
            for uri in sorted(related_uris, key=self._local_name)
        )
        return EntityContextContract(root_facade, related_facades)

    @staticmethod
    def ontology_text(filename: str) -> str:
        return (
            files("infobim.context")
            .joinpath("ontology", filename)
            .read_text(encoding="utf-8")
        )

    def _graph(self, filename: str) -> Graph:
        graph = Graph()
        graph.parse(data=self.ontology_text(filename), format="turtle")
        return graph

    def _resolve_entity_uri(
        self,
        entity: str,
        ns_graph: Graph,
        view_graph: Graph,
    ) -> URIRef:
        normalized = self._normalized_name(self._local_name(entity))
        candidates = {
            value
            for graph in (ns_graph, view_graph)
            for value in (*graph.subjects(), *graph.objects())
            if isinstance(value, URIRef)
            and self._normalized_name(self._local_name(value)) == normalized
        }
        if not candidates:
            raise ValueError(f"InfoBIM entity class not found: {entity}")
        return sorted(
            candidates,
            key=lambda uri: (
                not str(uri).startswith("https://infobim.org/ontology/ns#"),
                str(uri),
            ),
        )[0]

    def _resolve_facade(
        self,
        entity_uri: URIRef,
        view_graph: Graph,
    ) -> EntityFacadeContract:
        facade_subjects = [
            facade
            for facade, predicate, target in view_graph.triples(
                (None, None, entity_uri)
            )
            if self._local_name(predicate) == "targetsClass"
            and isinstance(facade, URIRef)
        ]
        if not facade_subjects:
            raise ValueError(
                "InfoBIM facade not found for entity class: "
                f"{self._local_name(entity_uri)}"
            )

        facade_uri = sorted(set(facade_subjects), key=str)[0]
        fields: List[FacadeFieldContract] = []
        for _, predicate, field_subject in view_graph.triples(
            (facade_uri, None, None)
        ):
            if self._local_name(predicate) != "hasFacadeField" or not isinstance(
                field_subject, URIRef
            ):
                continue
            identifier = self._first_literal(
                view_graph, field_subject, "identifier"
            )
            if identifier is None:
                continue
            datatype = self._first_uri(
                view_graph, field_subject, "fieldDatatype"
            )
            order = self._first_literal(
                view_graph, field_subject, "fieldOrder"
            )
            is_identifier = self._first_literal(
                view_graph, field_subject, "isIdentifierField"
            )
            fields.append(
                FacadeFieldContract(
                    name=str(identifier),
                    datatype=(self._local_name(datatype) if datatype else "string"),
                    order=int(str(order or "0")),
                    identifier=str(is_identifier or "false").lower() == "true",
                )
            )
        fields.sort(key=lambda field: (field.order, field.name))
        if not fields:
            raise ValueError(f"InfoBIM facade has no fields: {facade_uri}")
        return EntityFacadeContract(
            entity_uri=str(entity_uri),
            entity_name=self._local_name(entity_uri),
            facade_uri=str(facade_uri),
            fields=tuple(fields),
        )

    @classmethod
    def _first_literal(
        cls, graph: Graph, subject: URIRef, local_name: str
    ) -> Optional[Literal]:
        return next(
            (
                value
                for _, predicate, value in graph.triples((subject, None, None))
                if cls._local_name(predicate) == local_name
                and isinstance(value, Literal)
            ),
            None,
        )

    @classmethod
    def _first_uri(
        cls, graph: Graph, subject: URIRef, local_name: str
    ) -> Optional[URIRef]:
        return next(
            (
                value
                for _, predicate, value in graph.triples((subject, None, None))
                if cls._local_name(predicate) == local_name
                and isinstance(value, URIRef)
            ),
            None,
        )

    @staticmethod
    def _normalized_name(value: str) -> str:
        return "".join(character for character in value.lower() if character.isalnum())

    @staticmethod
    def _local_name(value: object) -> str:
        raw = str(value)
        if "#" in raw:
            return raw.rsplit("#", 1)[-1]
        return raw.rstrip("/").rsplit("/", 1)[-1]
