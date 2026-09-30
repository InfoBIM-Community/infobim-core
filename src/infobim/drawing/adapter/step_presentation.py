from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from infobim.drawing.adapter.taxonomy import DrawingViewNamespaces


class OntoStepPresentation:
    """
    Declare OntoSTEP / STP2OWL presentation entities.

    A sheet is a ``presentation_area``, each view drawn on it a
    ``presentation_view``, and a ``representation_relationship`` relates
    the area (``rep_1``) to each of its views (``rep_2``).
    """

    @staticmethod
    def presentation_area(graph: Graph, area: URIRef, name: str) -> None:
        step: Namespace = DrawingViewNamespaces.STEP
        graph.add((area, RDF.type, step.presentation_area))
        graph.add((area, step.name, Literal(name, datatype=XSD.string)))

    @staticmethod
    def presentation_view(graph: Graph, view: URIRef, name: str) -> None:
        step: Namespace = DrawingViewNamespaces.STEP
        graph.add((view, RDF.type, step.presentation_view))
        graph.add((view, step.name, Literal(name, datatype=XSD.string)))

    @staticmethod
    def representation_relationship(
        graph: Graph,
        relationship: URIRef,
        area: URIRef,
        view: URIRef,
    ) -> None:
        step: Namespace = DrawingViewNamespaces.STEP
        graph.add((relationship, RDF.type, step.representation_relationship))
        graph.add((relationship, step.rep_1, area))
        graph.add((relationship, step.rep_2, view))
