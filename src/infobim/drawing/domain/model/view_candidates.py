from typing import ClassVar, Dict, List, Optional, Tuple

from infobim.drawing.domain.model.view import (
    DrawingBoundary,
    DrawingViewTitle,
    DrawingViewCandidate,
    DrawingViewEvidence,
    DrawingViewReference,
    DrawingViewReferenceRole,
)


class DrawingViewCandidates:
    """
    The one collection of Drawing View candidates every strategy refines.

    Consolidation policy:

    * a region (viewport, frame or cluster) is the same view as a located
      candidate when both rectangles cover each other almost entirely and
      have a comparable size; it then enriches that candidate, and the more
      explicit source keeps the boundary (viewport, then frame, then
      cluster);
    * a region absorbs the unlocated candidates (a title or a label read
      before any region was known) whose anchor lies inside it or within
      reach of its edge;
    * a title or a reference joins the smallest located candidate that holds
      it, or the nearest one within reach; a view keeps a single title, the
      one written larger;
    * a label that no candidate holds opens an unlocated candidate of its
      own, and a marker that no candidate holds waits for a region.

    Titles are never compared to decide identity: a view is where it is.
    """

    SAME_REGION_OVERLAP: ClassVar[float] = 0.8
    SAME_REGION_AREA_RATIO: ClassVar[float] = 0.5
    REACH_IN_TEXT_HEIGHTS: ClassVar[float] = 4.0
    REACH_IN_DIAGONALS: ClassVar[float] = 0.1
    BOUNDARY_PRIORITY: ClassVar[Dict[DrawingViewEvidence, int]] = {
        DrawingViewEvidence.VIEWPORT: 0,
        DrawingViewEvidence.FRAME: 1,
        DrawingViewEvidence.CLUSTER: 2,
    }

    def __init__(self) -> None:
        self._candidates: List[DrawingViewCandidate] = []
        self._pending_markers: List[DrawingViewReference] = []

    def located(self) -> List[DrawingViewCandidate]:
        return [
            candidate for candidate in self._candidates if candidate.boundary is not None
        ]

    def unlocated(self) -> List[DrawingViewCandidate]:
        return [candidate for candidate in self._candidates if candidate.boundary is None]

    def titles(self) -> List[DrawingViewTitle]:
        return [
            candidate.title
            for candidate in self._candidates
            if candidate.title is not None
        ]

    def add_region(
        self,
        boundary: DrawingBoundary,
        evidence: DrawingViewEvidence,
        scale: Optional[str] = None,
    ) -> DrawingViewCandidate:
        """Add a delimited region, merging it with the view it already is."""
        if evidence not in self.BOUNDARY_PRIORITY:
            raise ValueError(f"{evidence.value} does not delimit a region.")

        candidate: Optional[DrawingViewCandidate] = self._same_region(boundary)
        if candidate is None:
            candidate = DrawingViewCandidate(boundary=boundary, boundary_source=evidence)
            self._candidates.append(candidate)
        elif self._outranks(evidence, candidate.boundary_source):
            candidate.boundary = boundary
            candidate.boundary_source = evidence
        candidate.record(evidence)
        if scale is not None and candidate.scale is None:
            candidate.scale = scale

        self._absorb_unlocated(candidate)
        self._attach_pending_markers(candidate)
        return candidate

    def add_title(self, title: DrawingViewTitle) -> None:
        """Give the title to the view that holds it, or keep it unlocated."""
        holder: Optional[DrawingViewCandidate] = self._holder_of(
            title.x, title.y, title.height
        )
        if holder is None:
            self._candidates.append(self._unlocated_titled(title))
            return

        displaced: Optional[DrawingViewTitle] = self._give_title(holder, title)
        if displaced is not None:
            self._candidates.append(self._unlocated_titled(displaced))

    def add_reference(self, reference: DrawingViewReference, text_height: float) -> None:
        """Attach a reference to the view that holds it."""
        holder: Optional[DrawingViewCandidate] = self._holder_of(
            reference.x, reference.y, text_height
        )
        if holder is None:
            holder = self._unlocated_near(reference.x, reference.y, text_height)
        if holder is not None:
            holder.references.append(reference)
            holder.record(DrawingViewEvidence.REFERENCE)
            if reference.role == DrawingViewReferenceRole.LABEL:
                holder.include(reference.boundary)
            return

        if reference.role == DrawingViewReferenceRole.LABEL:
            candidate: DrawingViewCandidate = DrawingViewCandidate(references=[reference])
            candidate.record(DrawingViewEvidence.REFERENCE)
            self._candidates.append(candidate)
            return

        self._pending_markers.append(reference)

    def add_cluster(self, boundary: DrawingBoundary) -> None:
        """Delimit, with a spatial cluster, the views nothing delimited yet."""
        self.add_region(boundary, DrawingViewEvidence.CLUSTER)

    def adopt_stray_unlocated(self) -> None:
        """
        Hang each still unlocated candidate on the nearest clustered view.

        A title written farther from its drawing than the cluster gap forms
        a cluster of text of its own; it still names the nearest drawing
        when it lies within reach of it.
        """
        clustered: List[DrawingViewCandidate] = [
            candidate
            for candidate in self.located()
            if candidate.boundary_source == DrawingViewEvidence.CLUSTER
        ]
        stray: DrawingViewCandidate
        for stray in self.unlocated():
            anchor: Optional[Tuple[float, float]] = stray.anchor()
            if anchor is None:
                continue
            open_views: List[DrawingViewCandidate] = [
                candidate
                for candidate in clustered
                if stray.title is None or candidate.title is None
            ]
            nearest: Optional[DrawingViewCandidate] = self._nearest_within_reach(
                open_views, anchor[0], anchor[1], self._text_height_of(stray)
            )
            if nearest is None:
                continue
            self._merge_into(nearest, stray)

    def _same_region(self, boundary: DrawingBoundary) -> Optional[DrawingViewCandidate]:
        candidate: DrawingViewCandidate
        for candidate in self.located():
            existing: DrawingBoundary = self._boundary_of(candidate)
            larger: float = max(existing.area, boundary.area)
            if larger <= 0.0:
                continue
            if (
                existing.overlap_ratio(boundary) >= self.SAME_REGION_OVERLAP
                and min(existing.area, boundary.area) / larger
                >= self.SAME_REGION_AREA_RATIO
            ):
                return candidate
        return None

    def _outranks(
        self,
        evidence: DrawingViewEvidence,
        current: Optional[DrawingViewEvidence],
    ) -> bool:
        if current is None:
            return True
        return self.BOUNDARY_PRIORITY[evidence] < self.BOUNDARY_PRIORITY[current]

    def _absorb_unlocated(self, region: DrawingViewCandidate) -> None:
        """
        Merge the unlocated candidates the region reaches, nearest first.

        A region that already carries a title leaves other titled
        candidates alone: they belong to a neighbouring view.
        """
        boundary: DrawingBoundary = self._boundary_of(region)
        reached: List[Tuple[float, DrawingViewCandidate]] = []
        unlocated: DrawingViewCandidate
        for unlocated in self.unlocated():
            anchor: Optional[Tuple[float, float]] = unlocated.anchor()
            if anchor is None:
                continue
            distance: float = boundary.distance_to_point(anchor[0], anchor[1])
            if distance <= self._reach(self._text_height_of(unlocated), boundary):
                reached.append((distance, unlocated))

        for _, unlocated in sorted(reached, key=lambda pair: pair[0]):
            if unlocated.title is not None and region.title is not None:
                continue
            self._merge_into(region, unlocated)

    def _attach_pending_markers(self, region: DrawingViewCandidate) -> None:
        boundary: DrawingBoundary = self._boundary_of(region)
        remaining: List[DrawingViewReference] = []
        marker: DrawingViewReference
        for marker in self._pending_markers:
            if boundary.contains_point(marker.x, marker.y):
                region.references.append(marker)
                region.record(DrawingViewEvidence.REFERENCE)
            else:
                remaining.append(marker)
        self._pending_markers = remaining

    def _merge_into(
        self,
        target: DrawingViewCandidate,
        source: DrawingViewCandidate,
    ) -> None:
        """Move what an unlocated candidate knows into a located one."""
        displaced: Optional[DrawingViewTitle] = None
        if source.title is not None:
            displaced = self._give_title(target, source.title)
        target.references.extend(source.references)
        reference: DrawingViewReference
        for reference in source.references:
            if reference.role == DrawingViewReferenceRole.LABEL:
                target.include(reference.boundary)
        evidence: DrawingViewEvidence
        for evidence in source.detected_by:
            target.record(evidence)
        self._candidates.remove(source)
        if displaced is not None:
            self._candidates.append(self._unlocated_titled(displaced))

    @staticmethod
    def _give_title(
        candidate: DrawingViewCandidate,
        title: DrawingViewTitle,
    ) -> Optional[DrawingViewTitle]:
        """Set the title, returning the one it displaced or refused."""
        candidate.record(DrawingViewEvidence.TITLE)
        if candidate.title is None:
            candidate.title = title
            candidate.include(title.boundary)
            return None
        if title.height > candidate.title.height:
            displaced: DrawingViewTitle = candidate.title
            candidate.title = title
            candidate.include(title.boundary)
            return displaced
        return title

    def _holder_of(
        self,
        x: float,
        y: float,
        text_height: float,
    ) -> Optional[DrawingViewCandidate]:
        holding: List[DrawingViewCandidate] = [
            candidate
            for candidate in self.located()
            if self._boundary_of(candidate).contains_point(x, y)
        ]
        if holding:
            return min(holding, key=lambda candidate: self._boundary_of(candidate).area)
        return self._nearest_within_reach(self.located(), x, y, text_height)

    def _unlocated_near(
        self,
        x: float,
        y: float,
        text_height: float,
    ) -> Optional[DrawingViewCandidate]:
        reach: float = self.REACH_IN_TEXT_HEIGHTS * text_height
        near: List[Tuple[float, DrawingViewCandidate]] = []
        candidate: DrawingViewCandidate
        for candidate in self.unlocated():
            anchor: Optional[Tuple[float, float]] = candidate.anchor()
            if anchor is None:
                continue
            distance: float = ((anchor[0] - x) ** 2 + (anchor[1] - y) ** 2) ** 0.5
            if distance <= reach:
                near.append((distance, candidate))
        if not near:
            return None
        return min(near, key=lambda pair: pair[0])[1]

    def _nearest_within_reach(
        self,
        candidates: List[DrawingViewCandidate],
        x: float,
        y: float,
        text_height: float,
    ) -> Optional[DrawingViewCandidate]:
        near: List[Tuple[float, DrawingViewCandidate]] = []
        candidate: DrawingViewCandidate
        for candidate in candidates:
            boundary: DrawingBoundary = self._boundary_of(candidate)
            distance: float = boundary.distance_to_point(x, y)
            if distance <= self._reach(text_height, boundary):
                near.append((distance, candidate))
        if not near:
            return None
        return min(near, key=lambda pair: pair[0])[1]

    def _reach(self, text_height: float, boundary: DrawingBoundary) -> float:
        return max(
            self.REACH_IN_TEXT_HEIGHTS * text_height,
            self.REACH_IN_DIAGONALS * boundary.diagonal,
        )

    @staticmethod
    def _unlocated_titled(title: DrawingViewTitle) -> DrawingViewCandidate:
        candidate: DrawingViewCandidate = DrawingViewCandidate(title=title)
        candidate.record(DrawingViewEvidence.TITLE)
        return candidate

    @staticmethod
    def _text_height_of(candidate: DrawingViewCandidate) -> float:
        if candidate.title is not None:
            return candidate.title.height
        return 0.0

    @staticmethod
    def _boundary_of(candidate: DrawingViewCandidate) -> DrawingBoundary:
        if candidate.boundary is None:
            raise ValueError("The candidate has no boundary yet.")
        return candidate.boundary
