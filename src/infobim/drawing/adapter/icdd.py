from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from infobim.drawing.adapter.taxonomy import DrawingViewNamespaces


class IcddDocuments:
    """Declare ICDD (ISO 21597-1) container documents."""

    @staticmethod
    def internal_document(graph: Graph, document: URIRef, filename: str) -> None:
        container: Namespace = DrawingViewNamespaces.CT
        graph.add((document, RDF.type, container.InternalDocument))
        graph.add((document, container.filename, Literal(filename, datatype=XSD.string)))


class IcddLinkset:
    """Declare ICDD (ISO 21597-1) link elements and directed binary links."""

    @staticmethod
    def link_element(graph: Graph, element: URIRef, document: URIRef) -> None:
        linkset: Namespace = DrawingViewNamespaces.LS
        graph.add((element, RDF.type, linkset.LinkElement))
        graph.add((element, linkset.hasDocument, document))

    @staticmethod
    def directed_binary_link(
        graph: Graph,
        link: URIRef,
        source: URIRef,
        target: URIRef,
    ) -> None:
        linkset: Namespace = DrawingViewNamespaces.LS
        graph.add((link, RDF.type, linkset.DirectedBinaryLink))
        graph.add((link, linkset.hasFromLinkElement, source))
        graph.add((link, linkset.hasToLinkElement, target))
