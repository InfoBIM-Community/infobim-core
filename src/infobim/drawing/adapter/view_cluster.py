from typing import ClassVar, Dict, List, Tuple
from statistics import median
from dataclasses import dataclass

from infobim.drawing.domain.model.view import DrawingBoundary
from infobim.drawing.domain.model.sheet import SheetEntity


@dataclass(frozen=True)
class DrawingSpatialCluster:
    """A group of entities lying close together, apart from the rest."""

    boundary: DrawingBoundary
    texts: Tuple[str, ...]
    has_geometry: bool


class DrawingSpatialClusters:
    """
    Group the entities no view holds yet into regions of the sheet.

    Two entities belong to the same region when the gap between their
    extents is at most the cluster gap: three text heights of the sheet,
    or one percent of its size when that is larger. Views on a sheet are
    set apart by empty space wider than the space inside them, so the
    regions this leaves are the views nothing else delimited.

    Entities that span most of the sheet in one direction, such as its
    border or its grid lines, would join every region into one and are
    left out, as are the entities inside the regions already delimited.
    """

    TEXT_HEIGHTS_OF_GAP: ClassVar[float] = 3.0
    SHEET_RATIO_OF_GAP: ClassVar[float] = 0.01
    SHEET_WIDE_RATIO: ClassVar[float] = 0.6

    @classmethod
    def of(
        cls,
        entities: List[SheetEntity],
        delimited: List[DrawingBoundary],
    ) -> List[DrawingSpatialCluster]:
        top_level: List[SheetEntity] = [
            entity for entity in entities if entity.is_top_level
        ]
        if not top_level:
            return []
        sheet: DrawingBoundary = cls._extents(top_level)
        loose: List[SheetEntity] = [
            entity
            for entity in top_level
            if not cls._is_sheet_wide(entity.boundary, sheet)
            and not any(
                boundary.contains_point(*entity.boundary.center) for boundary in delimited
            )
        ]
        if not loose:
            return []

        gap: float = cls._gap(entities, sheet)
        if gap <= 0.0:
            return [cls._cluster(loose)]
        parents: List[int] = list(range(len(loose)))
        cls._join_near(loose, parents, gap)
        groups: Dict[int, List[SheetEntity]] = {}
        index: int
        for index, entity in enumerate(loose):
            groups.setdefault(cls._root(parents, index), []).append(entity)
        return [cls._cluster(group) for group in groups.values()]

    @classmethod
    def _join_near(
        cls,
        entities: List[SheetEntity],
        parents: List[int],
        gap: float,
    ) -> None:
        """Union every pair closer than the gap, through a grid of gap-wide cells."""
        cells: Dict[Tuple[int, int], List[int]] = {}
        index: int
        entity: SheetEntity
        for index, entity in enumerate(entities):
            for cell in cls._cells(entity.boundary.expanded(gap / 2.0), gap):
                cells.setdefault(cell, []).append(index)
        members: List[int]
        for members in cells.values():
            first: int
            for position, first in enumerate(members):
                second: int
                for second in members[position + 1 :]:
                    if cls._root(parents, first) == cls._root(parents, second):
                        continue
                    if entities[first].boundary.gap_to(entities[second].boundary) <= gap:
                        parents[cls._root(parents, first)] = cls._root(parents, second)

    @staticmethod
    def _cells(boundary: DrawingBoundary, size: float) -> List[Tuple[int, int]]:
        return [
            (column, row)
            for column in range(int(boundary.min_x // size), int(boundary.max_x // size) + 1)
            for row in range(int(boundary.min_y // size), int(boundary.max_y // size) + 1)
        ]

    @staticmethod
    def _root(parents: List[int], index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    @staticmethod
    def _cluster(group: List[SheetEntity]) -> DrawingSpatialCluster:
        boundary: DrawingBoundary = group[0].boundary
        entity: SheetEntity
        for entity in group[1:]:
            boundary = boundary.union(entity.boundary)
        return DrawingSpatialCluster(
            boundary=boundary,
            texts=tuple(entity.text for entity in group if entity.text is not None),
            has_geometry=any(not entity.is_text for entity in group),
        )

    @classmethod
    def _gap(cls, entities: List[SheetEntity], sheet: DrawingBoundary) -> float:
        heights: List[float] = [
            entity.text_height
            for entity in entities
            if entity.text_height is not None and entity.text_height > 0.0
        ]
        sheet_gap: float = cls.SHEET_RATIO_OF_GAP * max(sheet.width, sheet.height)
        if not heights:
            return sheet_gap
        return max(cls.TEXT_HEIGHTS_OF_GAP * median(heights), sheet_gap)

    @classmethod
    def _is_sheet_wide(cls, boundary: DrawingBoundary, sheet: DrawingBoundary) -> bool:
        return (
            boundary.width >= cls.SHEET_WIDE_RATIO * sheet.width
            or boundary.height >= cls.SHEET_WIDE_RATIO * sheet.height
        )

    @staticmethod
    def _extents(entities: List[SheetEntity]) -> DrawingBoundary:
        boundary: DrawingBoundary = entities[0].boundary
        entity: SheetEntity
        for entity in entities[1:]:
            boundary = boundary.union(entity.boundary)
        return boundary
