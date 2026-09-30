from typing import Dict, List, Optional, Tuple

from infobim.drawing.adapter.taxonomy import DrawingViewVocabulary
from infobim.drawing.domain.model.view import (
    DrawingViewKind,
    DrawingViewReference,
    DrawingViewReferenceRole,
)
from infobim.drawing.domain.model.sheet import SheetEntity


class DrawingViewReferenceReader:
    """
    Read the graphic references drawn on a sheet.

    * a text such as ``A-A`` labels the section it is written under;
    * a short text inside a circle is a bubble pointing at another view;
    * a block reference whose name reads as a section, elevation or detail
      mark points at the view it names, labelled by its attributes.

    Each reference comes with the height it is written at, which is how
    far the consolidation lets it reach for a view.
    """

    @classmethod
    def references(
        cls,
        entities: List[SheetEntity],
    ) -> List[Tuple[DrawingViewReference, float]]:
        return (
            cls._pair_labels(entities)
            + cls._bubbles(entities)
            + cls._marker_blocks(entities)
        )

    @classmethod
    def _pair_labels(
        cls,
        entities: List[SheetEntity],
    ) -> List[Tuple[DrawingViewReference, float]]:
        return [
            (
                cls._reference(
                    entity,
                    DrawingViewKind.SECTION_VIEW,
                    DrawingViewReferenceRole.LABEL,
                ),
                cls._height(entity),
            )
            for entity in entities
            if entity.text is not None
            and entity.is_top_level
            and DrawingViewVocabulary.is_pair_label(entity.text)
        ]

    @classmethod
    def _bubbles(
        cls,
        entities: List[SheetEntity],
    ) -> List[Tuple[DrawingViewReference, float]]:
        circles: List[SheetEntity] = [
            entity for entity in entities if entity.radius is not None
        ]
        bubbles: List[Tuple[DrawingViewReference, float]] = []
        entity: SheetEntity
        for entity in entities:
            if entity.text is None or not DrawingViewVocabulary.is_bubble_label(
                entity.text
            ):
                continue
            center: Tuple[float, float] = entity.boundary.center
            if any(circle.boundary.contains_point(*center) for circle in circles):
                bubbles.append(
                    (
                        cls._reference(
                            entity,
                            DrawingViewKind.DETAIL_VIEW,
                            DrawingViewReferenceRole.MARKER,
                        ),
                        cls._height(entity),
                    )
                )
        return bubbles

    @classmethod
    def _marker_blocks(
        cls,
        entities: List[SheetEntity],
    ) -> List[Tuple[DrawingViewReference, float]]:
        labels: Dict[str, List[str]] = {}
        entity: SheetEntity
        for entity in entities:
            if entity.owner_handle is not None and entity.text:
                labels.setdefault(entity.owner_handle, []).append(entity.text)

        markers: List[Tuple[DrawingViewReference, float]] = []
        for entity in entities:
            if entity.block_name is None:
                continue
            kind: Optional[DrawingViewKind] = DrawingViewVocabulary.marker_kind_of_block(
                entity.block_name
            )
            if kind is None:
                continue
            center: Tuple[float, float] = entity.boundary.center
            label: str = (
                " ".join(labels[entity.handle])
                if entity.handle in labels
                else entity.block_name
            )
            markers.append(
                (
                    DrawingViewReference(
                        label=label,
                        kind=kind,
                        role=DrawingViewReferenceRole.MARKER,
                        x=center[0],
                        y=center[1],
                        boundary=entity.boundary,
                    ),
                    entity.boundary.height,
                )
            )
        return markers

    @classmethod
    def _reference(
        cls,
        entity: SheetEntity,
        kind: DrawingViewKind,
        role: DrawingViewReferenceRole,
    ) -> DrawingViewReference:
        if entity.text is None:
            raise ValueError(f"Entity {entity.handle} carries no text.")
        center: Tuple[float, float] = entity.boundary.center
        return DrawingViewReference(
            label=" ".join(entity.text.split()),
            kind=kind,
            role=role,
            x=center[0],
            y=center[1],
            boundary=entity.boundary,
        )

    @staticmethod
    def _height(entity: SheetEntity) -> float:
        if entity.text_height is None:
            raise ValueError(f"Text {entity.handle} carries no height.")
        return entity.text_height
