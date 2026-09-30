from typing import ClassVar
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.document import Drawing
from ezdxf.addons.drawing import Frontend, RenderContext, layout, pymupdf
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration

from infobim.drawing.domain.exception.preview import DrawingViewPreviewEmptyError


class DxfPreviewRenderer:
    """
    Render a DXF into a PNG thumbnail, in memory.

    The model space is drawn by ezdxf's drawing frontend into its PyMuPDF
    backend, dark on a light background, on a page shaped like the drawing
    so the view keeps its proportions. The longer side of the page is fixed,
    which bounds the image size whatever the drawing units are: this is a
    preview to recognise a view, not an engineering rendering. A view whose
    entities draw nothing, such as proxy entities the extraction could not
    copy or entities on hidden layers, has no preview.
    """

    FORMAT: ClassVar[str] = "png"
    LONG_SIDE_MM: ClassVar[float] = 160.0
    MIN_SIDE_MM: ClassVar[float] = 20.0
    MARGIN_MM: ClassVar[float] = 4.0
    DPI: ClassVar[int] = 150
    CONFIGURATION: ClassVar[Configuration] = Configuration(
        background_policy=BackgroundPolicy.WHITE,
        color_policy=ColorPolicy.BLACK,
    )

    def render(self, dxf_path: Path) -> bytes:
        document: Drawing = ezdxf.readfile(str(dxf_path))
        backend: pymupdf.PyMuPdfBackend = pymupdf.PyMuPdfBackend()
        Frontend(RenderContext(document), backend, config=self.CONFIGURATION).draw_layout(
            document.modelspace(), finalize=True
        )
        if not backend.player().bbox().has_data:
            raise DrawingViewPreviewEmptyError(
                f"{dxf_path.name} holds nothing that can be drawn."
            )
        return backend.get_pixmap_bytes(
            self._page_for(document),
            fmt=self.FORMAT,
            settings=layout.Settings(fit_page=True),
            dpi=self.DPI,
        )

    def _page_for(self, document: Drawing) -> layout.Page:
        extents: bbox.BoundingBox = bbox.extents(document.modelspace())
        margins: layout.Margins = layout.Margins.all(self.MARGIN_MM)
        if not extents.has_data or extents.size.x <= 0.0 or extents.size.y <= 0.0:
            return layout.Page(self.LONG_SIDE_MM, self.LONG_SIDE_MM, margins=margins)

        width: float = float(extents.size.x)
        height: float = float(extents.size.y)
        if width >= height:
            return layout.Page(
                self.LONG_SIDE_MM,
                max(self.MIN_SIDE_MM, self.LONG_SIDE_MM * height / width),
                margins=margins,
            )
        return layout.Page(
            max(self.MIN_SIDE_MM, self.LONG_SIDE_MM * width / height),
            self.LONG_SIDE_MM,
            margins=margins,
        )
