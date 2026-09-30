from typing import ClassVar
from pathlib import Path
from urllib.parse import quote

from rdflib import URIRef

from infobim.drawing.domain.model.view import DrawingView


class DrawingViewIris:
    """
    Deterministic IRIs of a sheet, its views and the links between them.

    Every IRI hangs from the project, named by its IfcProject GlobalId, and
    from the sheet, named by the SHA-256 of its bytes, so the same sheet in
    the same project always gets the same IRIs. A view is named by the
    file it was extracted into, which is unique among the views of a
    sheet, percent-encoded as it is so no two views share an IRI.
    """

    SCHEME: ClassVar[str] = "urn:infobim:project/"

    def __init__(self, project_global_id: str, sheet_identifier: str) -> None:
        self._project: str = quote(project_global_id, safe="")
        self._sheet: str = sheet_identifier

    def sheet_document(self) -> URIRef:
        return self._iri("document")

    def view_document(self, view: DrawingView) -> URIRef:
        return self._iri("document", self._key(view))

    def sheet_link_element(self) -> URIRef:
        return self._iri("link", "sheet")

    def view_link_element(self, view: DrawingView) -> URIRef:
        return self._iri("link", "view", self._key(view))

    def sheet_to_view_link(self, view: DrawingView) -> URIRef:
        return self._iri("link", "sheet-to-view", self._key(view))

    def presentation_area(self) -> URIRef:
        return self._iri("step")

    def presentation_view(self, view: DrawingView) -> URIRef:
        return self._iri("step", "view", self._key(view))

    def representation_relationship(self, view: DrawingView) -> URIRef:
        return self._iri("step", "relationship", self._key(view))

    def _iri(self, family: str, *segments: str) -> URIRef:
        tail: str = "".join(f"/{segment}" for segment in segments)
        return URIRef(f"{self.SCHEME}{self._project}/{family}/{self._sheet}{tail}")

    @staticmethod
    def _key(view: DrawingView) -> str:
        if view.path is None:
            raise ValueError(f"The view {view.title!r} was not extracted into a file.")
        return quote(Path(view.path).stem, safe="")
