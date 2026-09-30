from abc import ABC, abstractmethod
from typing import ClassVar, Dict, List, Optional, Tuple

from infobim.drawing.adapter.taxonomy import DrawingViewVocabulary
from infobim.drawing.domain.model.view import (
    DrawingView,
    DrawingBoundary,
    DrawingViewKind,
    DrawingViewCandidate,
    DrawingViewReferenceRole,
)


class DrawingViewClassificationRule(ABC):
    """One way of telling what kind of view a located candidate is."""

    @abstractmethod
    def kind_of(self, candidate: DrawingViewCandidate) -> Optional[DrawingViewKind]:
        """Return the kind this rule reads, or None when it has no opinion."""
        ...


class TitleClassificationRule(DrawingViewClassificationRule):
    """A title starting with a view word says the kind of its view."""

    def kind_of(self, candidate: DrawingViewCandidate) -> Optional[DrawingViewKind]:
        if candidate.title is None:
            return None
        return DrawingViewVocabulary.kind_of_title(candidate.title.text)


class LabelClassificationRule(DrawingViewClassificationRule):
    """A label such as ``A-A`` names the section it is written under."""

    def kind_of(self, candidate: DrawingViewCandidate) -> Optional[DrawingViewKind]:
        kinds: List[DrawingViewKind] = [
            reference.kind
            for reference in candidate.references
            if reference.role == DrawingViewReferenceRole.LABEL
        ]
        if not kinds:
            return None
        return kinds[0]


class MarkerClassificationRule(DrawingViewClassificationRule):
    """
    A view that carries section or elevation marks is the plan they cut.

    Section cuts and elevation marks are drawn over plans, pointing at the
    views they name; a detail bubble can be drawn over any view and says
    nothing of the view that carries it.
    """

    PLAN_MARKER_KINDS: ClassVar[Tuple[DrawingViewKind, ...]] = (
        DrawingViewKind.SECTION_VIEW,
        DrawingViewKind.ELEVATION_VIEW,
    )

    def kind_of(self, candidate: DrawingViewCandidate) -> Optional[DrawingViewKind]:
        if any(
            reference.role == DrawingViewReferenceRole.MARKER
            and reference.kind in self.PLAN_MARKER_KINDS
            for reference in candidate.references
        ):
            return DrawingViewKind.PLAN_VIEW
        return None


class DrawingViewClassifier:
    """
    Classify located candidates, asking each rule in turn.

    The rules read the evidence the discovery gathered and never the
    boundary: a view is delimited first and classified afterwards, and a
    view none of them recognises stays ``UNCLASSIFIED``.
    """

    def __init__(
        self,
        rules: Optional[List[DrawingViewClassificationRule]] = None,
    ) -> None:
        self._rules: List[DrawingViewClassificationRule] = (
            rules
            if rules is not None
            else [
                TitleClassificationRule(),
                LabelClassificationRule(),
                MarkerClassificationRule(),
            ]
        )

    def kind_of(self, candidate: DrawingViewCandidate) -> DrawingViewKind:
        rule: DrawingViewClassificationRule
        for rule in self._rules:
            kind: Optional[DrawingViewKind] = rule.kind_of(candidate)
            if kind is not None:
                return kind
        return DrawingViewKind.UNCLASSIFIED


class DrawingViewSettlement:
    """
    Turn the located candidates into the Drawing Views of the sheet.

    Views are ordered as a sheet is read, top to bottom and left to right.
    A view keeps its title as written, or the text of the label that names
    it; a view with neither is titled after its kind and its position
    among the views of that kind, and marked as carrying a generated title.
    """

    GENERATED_TITLE_FORMAT: ClassVar[str] = "{kind} {index:03d}"

    def __init__(self, classifier: DrawingViewClassifier) -> None:
        self._classifier: DrawingViewClassifier = classifier

    def views(self, candidates: List[DrawingViewCandidate]) -> List[DrawingView]:
        generated: Dict[DrawingViewKind, int] = {}
        views: List[DrawingView] = []
        candidate: DrawingViewCandidate
        for candidate in sorted(candidates, key=self._reading_order):
            kind: DrawingViewKind = self._classifier.kind_of(candidate)
            title: Optional[str] = self._title_of(candidate)
            if title is None:
                generated[kind] = generated.get(kind, 0) + 1
                title = self.GENERATED_TITLE_FORMAT.format(
                    kind=kind.value, index=generated[kind]
                )
            views.append(
                DrawingView(
                    title=title,
                    title_generated=self._title_of(candidate) is None,
                    kind=kind,
                    scale=self._scale_of(candidate),
                    boundary=self._boundary_of(candidate),
                    detected_by=tuple(candidate.detected_by),
                )
            )
        return views

    @staticmethod
    def _scale_of(candidate: DrawingViewCandidate) -> Optional[str]:
        """The scale written under the title, or the one its viewport states."""
        if candidate.title is not None and candidate.title.scale is not None:
            return candidate.title.scale
        return candidate.scale

    @staticmethod
    def _title_of(candidate: DrawingViewCandidate) -> Optional[str]:
        if candidate.title is not None:
            return candidate.title.text
        labels: List[str] = [
            reference.label
            for reference in candidate.references
            if reference.role == DrawingViewReferenceRole.LABEL
        ]
        if labels:
            return labels[0]
        return None

    @classmethod
    def _reading_order(cls, candidate: DrawingViewCandidate) -> Tuple[float, float]:
        boundary: DrawingBoundary = cls._boundary_of(candidate)
        return (-boundary.max_y, boundary.min_x)

    @staticmethod
    def _boundary_of(candidate: DrawingViewCandidate) -> DrawingBoundary:
        if candidate.boundary is None:
            raise ValueError("Only located candidates settle into Drawing Views.")
        return candidate.boundary
