"""Convert a local DXF file into a cached, content-addressed IFCX payload."""

import json
from typing import ClassVar, List
from pathlib import Path

import ezdxf
from ezdxf.layouts import Paperspace
from ezdxf.document import Drawing

from infobim.drawing.adapter.dxf import DxfConversion, DxfConverter
from infobim.drawing.adapter.viewport_projection import ViewportProjection
from infobim.drawing.adapter.transformation_payload import TransformationPayloadPath


class DxfToIfcxConverter:
    """Independent DXF -> IFCX transformation, cached by source content.

    A DXF's own structure says unambiguously which conversion applies,
    so there is nothing for a caller to choose between: a source with
    exactly one prancha -- a paper-space layout carrying at least one
    real viewport, not merely present in the layout table -- is
    converted as a flat snapshot of that layout (its own entities plus,
    through each of its viewports, the Model geometry it frames); a
    source with none is converted from its modelspace directly, the way
    a plain DXF with no real print setup of its own is meant to be
    read. Checking for a real viewport, not just a paper-space layout's
    presence, matters because every DXF has at least one paper-space
    layout by format convention -- ezdxf.new() alone creates an empty
    "Layout1" nobody configured -- so presence alone would treat nearly
    every plain DXF as a prancha to snapshot instead of a drawing to
    convert directly. More than one prancha is a caller error --
    DxfLayoutSplitter's own output never has more than one -- not a
    case to guess through.

    No drawing placement is applied in either case: that setting is
    specific to a Project's own .__infobim__/3d.json, which this
    standalone conversion does not read, so the drawing is placed at the
    identity transform.
    """

    SOURCE_FORMAT: ClassVar[str] = "dxf"
    TARGET_FORMAT: ClassVar[str] = "ifcx"

    def convert(self, container: Path, source: Path) -> Path:
        if source.suffix.lower() != ".dxf":
            raise ValueError(f"Not a DXF file: {source}")
        if not source.is_file():
            raise ValueError(f"Source DXF file is missing: {source}")

        identifier: str = TransformationPayloadPath.identifier_for(source)
        destination: Path = TransformationPayloadPath.resolve(
            container, self.SOURCE_FORMAT, self.TARGET_FORMAT, identifier, ".ifcx",
        )
        if destination.is_file():
            return destination

        conversion: DxfConversion = self._convert(source, identifier)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(conversion.document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return destination

    @classmethod
    def _convert(cls, source: Path, identifier: str) -> DxfConversion:
        drawing: Drawing = ezdxf.readfile(source)
        prancha_names: List[str] = [
            name
            for name in drawing.layout_names()
            if drawing.layout(name).is_any_paperspace
            and cls._has_real_viewport(drawing.layout(name))
        ]
        if len(prancha_names) > 1:
            raise ValueError(
                f"Expected at most one prancha layout to snapshot in "
                f"{source}, found {prancha_names}."
            )
        if len(prancha_names) == 1:
            return DxfConverter.from_layout(
                drawing, prancha_names[0], source.name, identifier
            )
        return DxfConverter.from_drawing(drawing, source.name, identifier)

    @staticmethod
    def _has_real_viewport(layout: Paperspace) -> bool:
        """
        A layout is a prancha only if it carries a real viewport -- one
        that is not id 1, paper space's own overall view by DXF
        convention (see ViewportProjection) -- not merely because a
        paper-space layout exists in the file at all.
        """
        return any(
            entity.dxftype() == "VIEWPORT"
            and entity.dxf.id != ViewportProjection.OVERALL_VIEWPORT_ID
            for entity in layout
        )
