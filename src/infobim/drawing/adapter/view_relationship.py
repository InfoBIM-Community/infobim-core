from typing import ClassVar, List, Tuple
from pathlib import Path
from dataclasses import dataclass

from rdflib import Graph, URIRef

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary

from infobim.drawing.adapter.icdd import IcddDocuments, IcddLinkset
from infobim.drawing.adapter.taxonomy import DrawingViewNamespaces
from infobim.drawing.adapter.view_iri import DrawingViewIris
from infobim.drawing.domain.model.view import DrawingView
from infobim.project.domain.model.contract import ProjectContract
from infobim.drawing.adapter.step_presentation import OntoStepPresentation


@dataclass(frozen=True)
class DrawingViewRelationshipGraphs:
    """
    The RDF that relates a sheet to its views.

    ``linkset`` holds the ICDD documents and the links from the sheet to
    each view; ``presentation`` holds their OntoSTEP presentation.
    """

    linkset: Graph
    presentation: Graph


class DrawingViewRelationshipModel:
    """
    Model a sheet and the views extracted from it.

    The sheet and every extracted view are ICDD internal documents, each
    with a link element; a directed binary link goes from the sheet's link
    element to each view's. The sheet is also a STEP presentation area and
    each view a presentation view, related by a representation
    relationship with the area as ``rep_1`` and the view as ``rep_2``.
    """

    @classmethod
    def of(
        cls,
        sheet: Path,
        views: List[DrawingView],
        iris: DrawingViewIris,
    ) -> DrawingViewRelationshipGraphs:
        linkset: Graph = cls._bound(Graph())
        presentation: Graph = cls._bound(Graph())

        sheet_document: URIRef = iris.sheet_document()
        sheet_element: URIRef = iris.sheet_link_element()
        area: URIRef = iris.presentation_area()
        IcddDocuments.internal_document(linkset, sheet_document, sheet.name)
        IcddLinkset.link_element(linkset, sheet_element, sheet_document)
        OntoStepPresentation.presentation_area(presentation, area, sheet.stem)

        view: DrawingView
        for view in views:
            view_document: URIRef = iris.view_document(view)
            view_element: URIRef = iris.view_link_element(view)
            IcddDocuments.internal_document(
                linkset, view_document, Path(cls._path_of(view)).name
            )
            IcddLinkset.link_element(linkset, view_element, view_document)
            IcddLinkset.directed_binary_link(
                linkset, iris.sheet_to_view_link(view), sheet_element, view_element
            )

            presentation_view: URIRef = iris.presentation_view(view)
            OntoStepPresentation.presentation_view(
                presentation, presentation_view, view.title
            )
            OntoStepPresentation.representation_relationship(
                presentation,
                iris.representation_relationship(view),
                area,
                presentation_view,
            )

        return DrawingViewRelationshipGraphs(linkset=linkset, presentation=presentation)

    @staticmethod
    def _bound(graph: Graph) -> Graph:
        graph.bind("ct", DrawingViewNamespaces.CT)
        graph.bind("ls", DrawingViewNamespaces.LS)
        graph.bind("step", DrawingViewNamespaces.STEP)
        return graph

    @staticmethod
    def _path_of(view: DrawingView) -> str:
        if view.path is None:
            raise ValueError(f"The view {view.title!r} was not extracted into a file.")
        return view.path


class DrawingViewRelationshipRepository:
    """
    Persist the relationships of a sheet in the project's ICDD dataset.

    The linkset goes to ``payload/linkset`` and the presentation triples to
    ``payload/triple`` of the reserved InfoBIM dataset, each in a file
    named after the identifier of the drawing the views were extracted
    from, the same one that names their DXF directory. Writing again for
    the same drawing replaces its files.
    """

    SUFFIX: ClassVar[str] = ".ttl"
    FORMAT: ClassVar[str] = "turtle"

    def __init__(self, project: Path, identifier: str) -> None:
        payload: Path = project / ProjectContract.DATASET_NAME / (
            ProjectContract.PAYLOAD_DIRECTORY_NAME
        )
        self._linkset_path: Path = (
            payload / ProjectContract.LINKSET_DIRECTORY_NAME / f"{identifier}{self.SUFFIX}"
        )
        self._presentation_path: Path = (
            payload / ProjectContract.TRIPLE_DIRECTORY_NAME / f"{identifier}{self.SUFFIX}"
        )

    @property
    def paths(self) -> Tuple[Path, Path]:
        return self._linkset_path, self._presentation_path

    def write(self, graphs: DrawingViewRelationshipGraphs) -> None:
        self._write(graphs.linkset, self._linkset_path)
        self._write(graphs.presentation, self._presentation_path)

    def read(self) -> Graph:
        """Read back, as one graph, what was persisted for the drawing."""
        graph: Graph = Graph()
        path: Path
        for path in self.paths:
            graph.parse(str(path), format=self.FORMAT)
        return graph

    def remove(self) -> None:
        path: Path
        for path in self.paths:
            path.unlink(missing_ok=True)

    def _write(self, graph: Graph, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(graph.serialize(format=self.FORMAT, encoding="utf-8"))


class DrawingViewShapes:
    """
    Load the canonical SHACL shapes the relationships must conform to.

    They are the AECO tool shapes of BrasidataCenter, read by their IRI like
    every other ontology.
    """

    @staticmethod
    def graph() -> Graph:
        """
        Raises:
            FileNotFoundError: the installed ontologies have no shapes at
                ``DrawingViewNamespaces.SHAPES_IRI``.
        """
        return BrasidataCenterOntologyLibrary().graph(DrawingViewNamespaces.SHAPES_IRI)
