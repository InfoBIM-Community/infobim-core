"""Split a DXF into one document per prancha (paper-space layout)."""

from typing import ClassVar, Dict, List
from pathlib import Path

import ezdxf
from ezdxf.bbox import extents
from ezdxf.math import BoundingBox, BoundingBox2d
from ezdxf.document import Drawing
from ezdxf.entities import DXFEntity

from infobim.project.domain.model.contract import ProjectContract
from infobim.drawing.adapter.viewport_projection import ViewportProjection


class DxfLayoutSplitter:
    """Split a DXF into one document per prancha (paper-space layout).

    A DXF's layouts are already the format's own native separation --
    Drawing.layout_names() lists them, and each is its own container of
    entities (Drawing.layout(name)), the same containers a CAD
    application's own layout tabs read from. No spatial or layer heuristic
    is needed to know which entity belongs to which layout: the DXF file
    already says so.

    Model is not a prancha and is never split out on its own: it is the
    combined drawing DwgToDxfConverter already wrote as <identifier>.dxf,
    so a "Model.dxf" here would only duplicate it. What each prancha keeps
    of Model is only the geometry that prancha's own viewports actually
    frame, computed via ViewportProjection.window() -- not the whole of
    Model.

    Each output starts as a full read of source, not a new document built
    up by copying entities into it: every block definition, layer,
    linetype and text style the kept layout depends on is already correct
    in source, so nothing needs to be re-resolved across documents. What
    is not the kept layout is deleted from that copy instead, and what of
    Model falls outside every one of that layout's viewport windows is
    destroyed the same way.

    source itself is deleted once every prancha has been produced from
    it: once split, it is superseded by its own per-prancha breakdown, and
    nothing reads it again afterward.
    """

    SOURCE_FORMAT: ClassVar[str] = "dwg"
    TARGET_FORMAT: ClassVar[str] = "dxf"
    MODEL_LAYOUT_NAME: ClassVar[str] = "Model"

    @classmethod
    def split(cls, container: Path, source: Path, identifier: str) -> Dict[str, Path]:
        """
        Split source into one document per prancha, filed under identifier.

        identifier is not derived from source's own bytes: it is the
        caller's identifier for the lineage this DXF belongs to (its source
        DWG's content hash, in the pipeline that produces source in the
        first place), so the split output stays addressed by that same
        identity rather than starting a new one for an intermediate file.

        source is removed once the split is complete: it is consumed by
        this call, not kept as a separate cached artifact alongside its
        own per-prancha breakdown.
        """
        if source.suffix.lower() != ".dxf":
            raise ValueError(f"Not a DXF file: {source}")
        if not source.is_file():
            raise ValueError(f"Source DXF file is missing: {source}")

        drawing: Drawing = ezdxf.readfile(source)
        layout_names: List[str] = [
            name
            for name in drawing.layout_names()
            if drawing.layout(name).is_any_paperspace
        ]

        result: Dict[str, Path] = {}
        for name in layout_names:
            destination: Path = cls._destination(container, identifier, name)
            if not destination.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                cls._keep_only(source, name, destination)
            result[name] = destination

        source.unlink(missing_ok=True)

        return result

    @classmethod
    def _keep_only(cls, source: Path, keep: str, destination: Path) -> None:
        """
        Save a copy of source with every paper-space layout but keep
        removed, and Model narrowed to only the geometry keep's own
        viewports actually frame.

        Viewport id 1 is excluded from the crop: by DXF/AutoCAD convention
        a layout's first viewport represents paper space's own overall
        view, not a floating window a drafter placed to frame a detail --
        every other viewport shares one view direction (top-down) that id
        1 does not.
        """
        drawing: Drawing = ezdxf.readfile(source)

        name: str
        for name in list(drawing.layout_names()):
            if name in (keep, cls.MODEL_LAYOUT_NAME):
                continue
            drawing.layouts.delete(name)

        windows: List[BoundingBox2d] = [
            ViewportProjection(entity).window()
            for entity in drawing.layout(keep)
            if entity.dxftype() == "VIEWPORT"
            and entity.dxf.id != ViewportProjection.OVERALL_VIEWPORT_ID
        ]

        entity: DXFEntity
        for entity in list(drawing.modelspace()):
            box: BoundingBox = extents([entity])
            if not box.has_data:
                continue
            entity_window: BoundingBox2d = BoundingBox2d([box.extmin, box.extmax])
            if not any(window.has_overlap(entity_window) for window in windows):
                entity.destroy()

        drawing.saveas(destination)

    @classmethod
    def _destination(cls, container: Path, identifier: str, layout_name: str) -> Path:
        """
        File the split under the same format/dwg/dxf/<identifier> space
        DwgToDxfConverter already writes <identifier>.dxf into, so a
        reader finds everything this DWG's DXF conversion produced -- the
        combined file and its per-prancha breakdown -- in one place.
        """
        return (
            container
            / ProjectContract.DATASET_NAME
            / "payload"
            / "document"
            / "etl"
            / "format"
            / cls.SOURCE_FORMAT
            / cls.TARGET_FORMAT
            / identifier
            / f"{layout_name}.dxf"
        )
