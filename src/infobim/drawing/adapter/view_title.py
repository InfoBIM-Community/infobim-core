from typing import ClassVar, List, Optional, Tuple

from infobim.drawing.adapter.taxonomy import DrawingViewVocabulary
from infobim.drawing.domain.model.view import DrawingViewTitle
from infobim.drawing.domain.model.sheet import SheetEntity


class DrawingViewTitleReader:
    """
    Read the texts of a sheet that name a Drawing View, with their scale.

    A title is a text that starts with one of the vocabulary's view words.
    The scale is read from the title itself when written in it, or from a
    scale-only text written next to it, within a few title heights.
    """

    SCALE_REACH_IN_TEXT_HEIGHTS: ClassVar[float] = 3.0

    @classmethod
    def titles(cls, entities: List[SheetEntity]) -> List[DrawingViewTitle]:
        texts: List[SheetEntity] = [entity for entity in entities if entity.is_text]
        titles: List[DrawingViewTitle] = [
            cls._title(entity)
            for entity in texts
            if DrawingViewVocabulary.kind_of_title(cls._text(entity)) is not None
        ]
        scales: List[Tuple[SheetEntity, str]] = []
        entity: SheetEntity
        for entity in texts:
            scale: Optional[str] = DrawingViewVocabulary.scale_only(cls._text(entity))
            if scale is not None:
                scales.append((entity, scale))
        return [cls._with_nearby_scale(title, scales) for title in titles]

    @classmethod
    def _title(cls, entity: SheetEntity) -> DrawingViewTitle:
        text: str = cls._text(entity)
        center: Tuple[float, float] = entity.boundary.center
        return DrawingViewTitle(
            text=DrawingViewVocabulary.title_without_scale(text),
            x=center[0],
            y=center[1],
            height=cls._height(entity),
            scale=DrawingViewVocabulary.scale_in(text),
            boundary=entity.boundary,
        )

    @classmethod
    def _with_nearby_scale(
        cls,
        title: DrawingViewTitle,
        scales: List[Tuple[SheetEntity, str]],
    ) -> DrawingViewTitle:
        if title.scale is not None:
            return title
        reach: float = cls.SCALE_REACH_IN_TEXT_HEIGHTS * title.height
        near: List[Tuple[float, SheetEntity, str]] = [
            (entity.boundary.distance_to_point(title.x, title.y), entity, scale)
            for entity, scale in scales
            if entity.boundary.distance_to_point(title.x, title.y) <= reach
        ]
        if not near:
            return title
        nearest: Tuple[float, SheetEntity, str] = min(near, key=lambda item: item[0])
        return DrawingViewTitle(
            text=title.text,
            x=title.x,
            y=title.y,
            height=title.height,
            scale=nearest[2],
            boundary=title.boundary.union(nearest[1].boundary),
        )

    @staticmethod
    def _text(entity: SheetEntity) -> str:
        if entity.text is None:
            raise ValueError(f"Entity {entity.handle} carries no text.")
        return entity.text

    @staticmethod
    def _height(entity: SheetEntity) -> float:
        if entity.text_height is None:
            raise ValueError(f"Text {entity.handle} carries no height.")
        return entity.text_height
