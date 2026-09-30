from typing import Optional
from dataclasses import dataclass

from infobim.drawing.domain.model.view import DrawingBoundary


@dataclass(frozen=True)
class SheetEntity:
    """
    One entity drawn in a sheet's model space, as view discovery reads it.

    ``owner_handle`` is set for the attributes of a block reference, which
    are read as texts of their own but belong to the reference that
    carries them.
    """

    handle: str
    dxftype: str
    boundary: DrawingBoundary
    text: Optional[str] = None
    text_height: Optional[float] = None
    block_name: Optional[str] = None
    rectangle: bool = False
    radius: Optional[float] = None
    owner_handle: Optional[str] = None

    @property
    def is_text(self) -> bool:
        return self.text is not None

    @property
    def is_top_level(self) -> bool:
        return self.owner_handle is None
