from typing import ClassVar, List

from infobim.drawing.adapter.taxonomy import DrawingViewVocabulary
from infobim.drawing.domain.model.view import DrawingBoundary, DrawingViewTitle
from infobim.drawing.domain.model.sheet import SheetEntity


class DrawingViewFrameFinder:
    """
    Find the drawn frames that delimit Drawing Views on a sheet.

    A frame is a closed rectangle, or a block reference whose name says it
    is a frame, that is plausible as the limit of a view:

    * it holds drawing: a few entities lie entirely inside it;
    * it is isolated: no entity crosses its edge, which is what tells a view
      frame from a room or a slab outline drawn inside a view;
    * it is not the sheet border: a rectangle holding several frames or
      several titles is the sheet itself, not one of its views;
    * it is not the title block: its texts do not read as one;
    * it is outermost: a frame drawn inside another frame is content of
      that view.
    """

    MIN_CONTENT: ClassVar[int] = 3
    EDGE_TOLERANCE_RATIO: ClassVar[float] = 0.005
    SHEET_MIN_HELD: ClassVar[int] = 2

    @classmethod
    def frames(
        cls,
        entities: List[SheetEntity],
        titles: List[DrawingViewTitle],
    ) -> List[DrawingBoundary]:
        top_level: List[SheetEntity] = [
            entity for entity in entities if entity.is_top_level
        ]
        plausible: List[SheetEntity] = [
            entity
            for entity in top_level
            if cls._is_outline(entity) and cls._holds_isolated_drawing(entity, top_level)
        ]
        frames: List[SheetEntity] = [
            frame
            for frame in plausible
            if not cls._is_sheet_border(frame, plausible, titles)
            and not cls._is_title_block(frame, entities, titles)
        ]
        return [
            frame.boundary
            for frame in frames
            if not any(
                other is not frame and cls._inside(frame.boundary, other.boundary)
                for other in frames
            )
        ]

    @staticmethod
    def _is_outline(entity: SheetEntity) -> bool:
        if entity.rectangle:
            return True
        return entity.block_name is not None and DrawingViewVocabulary.is_frame_block(
            entity.block_name
        )

    @classmethod
    def _holds_isolated_drawing(
        cls,
        frame: SheetEntity,
        entities: List[SheetEntity],
    ) -> bool:
        tolerance: float = cls._tolerance(frame.boundary)
        held: int = 0
        entity: SheetEntity
        for entity in entities:
            if entity is frame or entity.boundary.contains(frame.boundary, tolerance):
                continue
            if frame.boundary.contains(entity.boundary, tolerance):
                held += 1
            elif cls._crosses(frame.boundary, entity.boundary, tolerance):
                return False
        return held >= cls.MIN_CONTENT

    @staticmethod
    def _crosses(
        frame: DrawingBoundary,
        boundary: DrawingBoundary,
        tolerance: float,
    ) -> bool:
        interior: DrawingBoundary = frame.expanded(-tolerance)
        return interior.gap_to(boundary) == 0.0

    @classmethod
    def _is_sheet_border(
        cls,
        frame: SheetEntity,
        plausible: List[SheetEntity],
        titles: List[DrawingViewTitle],
    ) -> bool:
        held_frames: int = sum(
            1
            for other in plausible
            if other is not frame and cls._inside(other.boundary, frame.boundary)
        )
        held_titles: int = sum(
            1 for title in titles if frame.boundary.contains_point(title.x, title.y)
        )
        return held_frames >= cls.SHEET_MIN_HELD or held_titles >= cls.SHEET_MIN_HELD

    @staticmethod
    def _is_title_block(
        frame: SheetEntity,
        entities: List[SheetEntity],
        titles: List[DrawingViewTitle],
    ) -> bool:
        if any(frame.boundary.contains_point(title.x, title.y) for title in titles):
            return False
        texts: List[str] = [
            entity.text
            for entity in entities
            if entity.text is not None and frame.boundary.contains(entity.boundary)
        ]
        return DrawingViewVocabulary.is_title_block(texts)

    @classmethod
    def _inside(cls, inner: DrawingBoundary, outer: DrawingBoundary) -> bool:
        return inner != outer and outer.contains(inner, cls._tolerance(outer))

    @classmethod
    def _tolerance(cls, boundary: DrawingBoundary) -> float:
        return cls.EDGE_TOLERANCE_RATIO * boundary.diagonal
