from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, replace


class DrawingViewKind(str, Enum):
    """What a Drawing View shows of the model it draws."""

    PLAN_VIEW = "PLAN_VIEW"
    SECTION_VIEW = "SECTION_VIEW"
    ELEVATION_VIEW = "ELEVATION_VIEW"
    DETAIL_VIEW = "DETAIL_VIEW"
    UNCLASSIFIED = "UNCLASSIFIED"


class DrawingViewEvidence(str, Enum):
    """The discovery strategy that contributed to a Drawing View."""

    VIEWPORT = "viewport"
    TITLE = "title"
    FRAME = "frame"
    REFERENCE = "reference"
    CLUSTER = "cluster"


class DrawingViewReferenceRole(str, Enum):
    """
    What a graphic reference says about the view it is found in.

    A ``LABEL`` names the view itself, as ``A-A`` under a section. A
    ``MARKER`` points at another view, as a section cut or a detail bubble
    drawn over a plan.
    """

    LABEL = "label"
    MARKER = "marker"


@dataclass(frozen=True)
class DrawingBoundary:
    """Axis-aligned rectangle of drawing coordinates a view occupies."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def diagonal(self) -> float:
        return (self.width ** 2 + self.height ** 2) ** 0.5

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)

    def contains_point(self, x: float, y: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def contains(self, other: "DrawingBoundary", tolerance: float = 0.0) -> bool:
        return (
            other.min_x >= self.min_x - tolerance
            and other.min_y >= self.min_y - tolerance
            and other.max_x <= self.max_x + tolerance
            and other.max_y <= self.max_y + tolerance
        )

    def intersection_area(self, other: "DrawingBoundary") -> float:
        width: float = min(self.max_x, other.max_x) - max(self.min_x, other.min_x)
        height: float = min(self.max_y, other.max_y) - max(self.min_y, other.min_y)
        if width <= 0.0 or height <= 0.0:
            return 0.0
        return width * height

    def overlap_ratio(self, other: "DrawingBoundary") -> float:
        """Share of the smaller of both rectangles that the other one covers."""
        smaller: float = min(self.area, other.area)
        if smaller <= 0.0:
            return 0.0
        return self.intersection_area(other) / smaller

    def gap_to(self, other: "DrawingBoundary") -> float:
        """Shortest distance between both rectangles; zero when they touch."""
        dx: float = max(other.min_x - self.max_x, self.min_x - other.max_x, 0.0)
        dy: float = max(other.min_y - self.max_y, self.min_y - other.max_y, 0.0)
        return (dx ** 2 + dy ** 2) ** 0.5

    def distance_to_point(self, x: float, y: float) -> float:
        return self.gap_to(DrawingBoundary(x, y, x, y))

    def union(self, other: "DrawingBoundary") -> "DrawingBoundary":
        return DrawingBoundary(
            min(self.min_x, other.min_x),
            min(self.min_y, other.min_y),
            max(self.max_x, other.max_x),
            max(self.max_y, other.max_y),
        )

    def expanded(self, margin: float) -> "DrawingBoundary":
        return DrawingBoundary(
            self.min_x - margin,
            self.min_y - margin,
            self.max_x + margin,
            self.max_y + margin,
        )

    def to_list(self) -> List[float]:
        return [self.min_x, self.min_y, self.max_x, self.max_y]


@dataclass(frozen=True)
class DrawingViewReference:
    """
    A graphic reference found on the sheet, such as ``A-A`` or a bubble.

    ``boundary`` is the extent the reference is drawn over.
    """

    label: str
    kind: DrawingViewKind
    role: DrawingViewReferenceRole
    x: float
    y: float
    boundary: DrawingBoundary


@dataclass(frozen=True)
class DrawingViewTitle:
    """
    A text that names a Drawing View, with the scale written next to it.

    ``boundary`` covers the title and, when written apart, its scale: both
    are drawn as part of the view they name.
    """

    text: str
    x: float
    y: float
    height: float
    scale: Optional[str]
    boundary: DrawingBoundary


@dataclass
class DrawingViewCandidate:
    """
    A Drawing View while it is still being discovered.

    Each strategy enriches the same candidate instead of producing one of
    its own: the boundary, the title and the references are filled in as
    evidence arrives, and ``detected_by`` records which strategies did.
    ``scale`` is the one a viewport states; a title states its own.
    """

    boundary: Optional[DrawingBoundary] = None
    boundary_source: Optional[DrawingViewEvidence] = None
    scale: Optional[str] = None
    title: Optional[DrawingViewTitle] = None
    references: List[DrawingViewReference] = field(default_factory=list)
    detected_by: List[DrawingViewEvidence] = field(default_factory=list)

    def anchor(self) -> Optional[Tuple[float, float]]:
        """The point that places a candidate that has no boundary yet."""
        if self.title is not None:
            return (self.title.x, self.title.y)
        labels: List[DrawingViewReference] = [
            reference
            for reference in self.references
            if reference.role == DrawingViewReferenceRole.LABEL
        ]
        if labels:
            return (labels[0].x, labels[0].y)
        return None

    def record(self, evidence: DrawingViewEvidence) -> None:
        if evidence not in self.detected_by:
            self.detected_by.append(evidence)

    def include(self, boundary: DrawingBoundary) -> None:
        """Widen a located candidate to what is drawn as part of it."""
        if self.boundary is not None:
            self.boundary = self.boundary.union(boundary)


@dataclass(frozen=True)
class DrawingView:
    """
    One view drawn on a sheet, as the discovery settled it.

    ``title_generated`` tells a title read from the drawing apart from the
    deterministic one given to a view that carries none. ``path`` is the
    DXF the view was extracted into, once it was.
    """

    title: str
    title_generated: bool
    kind: DrawingViewKind
    scale: Optional[str]
    boundary: DrawingBoundary
    detected_by: Tuple[DrawingViewEvidence, ...]
    path: Optional[str] = None

    def extracted_to(self, path: str) -> "DrawingView":
        return replace(self, path=path)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "title_generated": self.title_generated,
            "kind": self.kind.value,
            "scale": self.scale,
            "boundary": self.boundary.to_list(),
            "path": self.path,
            "detected_by": [evidence.value for evidence in self.detected_by],
        }
