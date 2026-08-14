import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class EntityLinksetField:
    """A workbook column mapped to one semantic facade field."""

    name: str
    facade_field_uri: str


@dataclass(frozen=True)
class EntityLinksetArtifact:
    """The generated ICDD Linkset artifact."""

    linkset_path: Path
    link_count: int


class EntityLinksetAdapter:
    """Generate an ISO 21597 ICDD Linkset for an entity workbook."""

    _CONTAINER_ONTOLOGY = (
        "https://standards.iso.org/iso/21597/-1/ed-1/en/Container"
    )
    _LINKSET_ONTOLOGY = (
        "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset"
    )

    def generate(
        self,
        *,
        container_path: Path,
        workbook_path: Path,
        worksheet_name: str,
        entity_name: str,
        facade_uri: str,
        fields: Sequence[EntityLinksetField],
    ) -> EntityLinksetArtifact:
        try:
            from rdflib import Graph, Literal, Namespace, URIRef
            from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, XSD
        except ModuleNotFoundError as exc:
            raise ValueError(
                "The 'rdflib' package is required to generate an ICDD linkset."
            ) from exc

        resolved_container_path = container_path.expanduser().resolve()
        resolved_workbook_path = workbook_path.expanduser().resolve()
        if not resolved_workbook_path.is_file():
            raise FileNotFoundError(
                f"Entity workbook not found: {resolved_workbook_path}"
            )
        if not entity_name.strip():
            raise ValueError("The entity name must not be empty.")
        if not fields:
            raise ValueError("At least one entity linkset field is required.")

        linkset_path = (
            resolved_container_path
            / ".__ontobdc__"
            / "linkset"
            / f"{entity_name}.ttl"
        )
        linkset_path.parent.mkdir(parents=True, exist_ok=True)

        CT = Namespace(f"{self._CONTAINER_ONTOLOGY}#")
        LS = Namespace(f"{self._LINKSET_ONTOLOGY}#")
        graph = Graph()
        graph.bind("ct", CT)
        graph.bind("dcterms", DCTERMS)
        graph.bind("ls", LS)
        graph.bind("owl", OWL)
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)

        slug = re.sub(r"[^0-9A-Za-z_-]+", "-", entity_name).strip("-").lower()
        base = f"urn:infobim:icdd:{slug}"
        ontology_uri = URIRef(f"{base}:linkset-ontology")
        linkset_uri = URIRef(f"{base}:linkset")
        workbook_uri = URIRef(f"{base}:document:workbook")
        facade_document_uri = URIRef(f"{base}:document:facade")

        graph.add((ontology_uri, RDF.type, OWL.Ontology))
        graph.add(
            (ontology_uri, OWL.imports, URIRef(self._CONTAINER_ONTOLOGY))
        )
        graph.add((ontology_uri, OWL.imports, URIRef(self._LINKSET_ONTOLOGY)))

        graph.add((linkset_uri, RDF.type, CT.Linkset))
        graph.add(
            (
                linkset_uri,
                CT.filename,
                Literal(
                    linkset_path.relative_to(resolved_container_path).as_posix()
                ),
            )
        )
        graph.add((linkset_uri, CT.filetype, Literal("ttl")))
        graph.add((linkset_uri, CT.name, Literal(linkset_path.name)))
        graph.add(
            (linkset_uri, DCTERMS.title, Literal(f"{entity_name} field linkset"))
        )

        relative_workbook_path = Path(
            os.path.relpath(
                resolved_workbook_path,
                start=resolved_container_path,
            )
        ).as_posix()
        graph.add((workbook_uri, RDF.type, CT.InternalDocument))
        graph.add((workbook_uri, CT.filename, Literal(relative_workbook_path)))
        graph.add((workbook_uri, CT.filetype, Literal("xlsx")))
        graph.add((workbook_uri, CT.name, Literal(resolved_workbook_path.name)))

        facade_document = facade_uri.split("#", maxsplit=1)[0]
        graph.add((facade_document_uri, RDF.type, CT.ExternalDocument))
        graph.add(
            (
                facade_document_uri,
                CT.url,
                Literal(facade_document, datatype=XSD.anyURI),
            )
        )
        graph.add((facade_document_uri, CT.name, Literal(f"{entity_name} facade")))

        for field in fields:
            token = re.sub(r"[^0-9A-Za-z_-]+", "-", field.name).strip("-").lower()
            workbook_element = URIRef(f"{base}:element:workbook:{token}")
            workbook_identifier = URIRef(f"{base}:identifier:workbook:{token}")
            facade_element = URIRef(f"{base}:element:facade:{token}")
            facade_identifier = URIRef(f"{base}:identifier:facade:{token}")
            link_uri = URIRef(f"{base}:link:{token}")

            graph.add((workbook_element, RDF.type, LS.LinkElement))
            graph.add((workbook_element, LS.hasDocument, workbook_uri))
            graph.add((workbook_element, LS.hasIdentifier, workbook_identifier))
            graph.add(
                (workbook_identifier, RDF.type, LS.StringBasedIdentifier)
            )
            graph.add((workbook_identifier, LS.identifier, Literal(field.name)))
            graph.add(
                (
                    workbook_identifier,
                    LS.identifierField,
                    Literal(f"{worksheet_name}.header"),
                )
            )

            graph.add((facade_element, RDF.type, LS.LinkElement))
            graph.add((facade_element, LS.hasDocument, facade_document_uri))
            graph.add((facade_element, LS.hasIdentifier, facade_identifier))
            graph.add((facade_identifier, RDF.type, LS.URIBasedIdentifier))
            graph.add(
                (
                    facade_identifier,
                    LS.uri,
                    Literal(field.facade_field_uri, datatype=XSD.anyURI),
                )
            )

            graph.add((link_uri, RDF.type, LS.DirectedBinaryLink))
            graph.add((link_uri, LS.hasFromLinkElement, workbook_element))
            graph.add((link_uri, LS.hasToLinkElement, facade_element))
            graph.add((link_uri, RDFS.label, Literal(field.name)))

        graph.serialize(destination=str(linkset_path), format="turtle")
        return EntityLinksetArtifact(
            linkset_path=linkset_path,
            link_count=len(fields),
        )
