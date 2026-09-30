from typing import ClassVar, List, Optional, Tuple

from ezdxf.layouts import Layout
from ezdxf.document import Drawing
from ezdxf.entities import Viewport

from infobim.drawing.domain.model.view import DrawingBoundary


class DxfViewportRegions:
    """
    Read the model-space regions the paper-space viewports of a sheet show.

    Each viewport shows a rectangle of model space centred on its view
    centre, as tall as its view height and as wide as its own aspect
    ratio makes it. Its scale is the ratio between the model height shown
    and the paper height it is drawn at. The overall viewport every paper
    space layout carries shows the layout itself, not a view, and is
    left out.
    """

    OVERALL_VIEWPORT_ID: ClassVar[int] = 1
    SCALE_DECIMALS: ClassVar[int] = 2

    @classmethod
    def of(cls, document: Drawing) -> List[Tuple[DrawingBoundary, Optional[str]]]:
        regions: List[Tuple[DrawingBoundary, Optional[str]]] = []
        layout: Layout
        for layout in document.layouts:
            if layout.is_modelspace:
                continue
            viewport: Viewport
            for viewport in layout.query("VIEWPORT"):
                region: Optional[Tuple[DrawingBoundary, Optional[str]]] = cls._region(
                    viewport
                )
                if region is not None:
                    regions.append(region)
        return regions

    @classmethod
    def _region(cls, viewport: Viewport) -> Optional[Tuple[DrawingBoundary, Optional[str]]]:
        if viewport.dxf.id == cls.OVERALL_VIEWPORT_ID:
            return None
        paper_width: float = float(viewport.dxf.width)
        paper_height: float = float(viewport.dxf.height)
        view_height: float = float(viewport.dxf.view_height)
        if paper_width <= 0.0 or paper_height <= 0.0 or view_height <= 0.0:
            return None

        view_width: float = view_height * paper_width / paper_height
        center_x: float = float(viewport.dxf.view_center_point.x)
        center_y: float = float(viewport.dxf.view_center_point.y)
        boundary: DrawingBoundary = DrawingBoundary(
            center_x - view_width / 2.0,
            center_y - view_height / 2.0,
            center_x + view_width / 2.0,
            center_y + view_height / 2.0,
        )
        return boundary, cls._scale(view_height / paper_height)

    @classmethod
    def _scale(cls, ratio: float) -> str:
        rounded: float = round(ratio, cls.SCALE_DECIMALS)
        if rounded == int(rounded):
            return f"1:{int(rounded)}"
        return f"1:{rounded}"
