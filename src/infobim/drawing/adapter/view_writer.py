import re
import shutil
from typing import ClassVar, Dict, List, Optional, Pattern, Set
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing
from ezdxf.entities import DXFGraphic
from ezdxf.addons.importer import Importer

from infobim.drawing.domain.model.view import DrawingView, DrawingBoundary
from infobim.drawing.domain.model.sheet import SheetEntity


class DrawingViewFileName:
    """
    Name the DXF a Drawing View is extracted into, after its title.

    Only what a file name cannot carry is changed: path separators and the
    characters Windows reserves become ``-``, control characters are
    dropped and trailing dots and spaces are trimmed. Names are compared
    without case, as case-insensitive filesystems do, and a repeated name
    gets `` (2)``, `` (3)``… in the order the views were settled.
    """

    SUFFIX: ClassVar[str] = ".dxf"
    RESERVED: ClassVar[Pattern[str]] = re.compile(r'[<>:"/\\|?*]')
    CONTROL: ClassVar[Pattern[str]] = re.compile(r"[\x00-\x1f\x7f]")
    MAX_STEM_BYTES: ClassVar[int] = 200

    def __init__(self) -> None:
        self._taken: Set[str] = set()

    def name_for(self, title: str) -> str:
        stem: str = self._sanitized(title)
        if not stem:
            raise ValueError(f"The title {title!r} leaves no character for a file name.")
        name: str = f"{stem}{self.SUFFIX}"
        copy: int = 1
        while name.lower() in self._taken:
            copy += 1
            name = f"{stem} ({copy}){self.SUFFIX}"
        self._taken.add(name.lower())
        return name

    @classmethod
    def _sanitized(cls, title: str) -> str:
        stem: str = cls.CONTROL.sub("", cls.RESERVED.sub("-", title)).strip()
        stem = stem.rstrip(". ")
        while len(stem.encode("utf-8")) > cls.MAX_STEM_BYTES:
            stem = stem[:-1]
        return stem.rstrip(". ")


class DxfDrawingViewWriter:
    """
    Write each Drawing View of a sheet into a DXF of its own.

    An entity belongs to the smallest view whose boundary, widened by a
    small margin, holds its whole extents; an entity no view holds, such as
    the sheet border, goes nowhere. The entities are imported with ezdxf's
    importer, which brings the layers, line types, text and dimension
    styles and block definitions they use, so the extracted DXF keeps its
    geometry, texts, dimensions, hatches and block references as drawn.

    The directory belongs to the extraction of one drawing content: what an
    earlier extraction of the same content left there is replaced, never
    mixed with the new files.
    """

    MARGIN_RATIO: ClassVar[float] = 0.02

    def write(
        self,
        document: Drawing,
        entities: List[SheetEntity],
        views: List[DrawingView],
        directory: Path,
    ) -> List[DrawingView]:
        members: Dict[int, List[str]] = self._members(entities, views)
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

        names: DrawingViewFileName = DrawingViewFileName()
        written: List[DrawingView] = []
        index: int
        view: DrawingView
        for index, view in enumerate(views):
            path: Path = directory / names.name_for(view.title)
            self._write_view(document, members[index], path)
            written.append(view.extracted_to(str(path)))
        return written

    def _members(
        self,
        entities: List[SheetEntity],
        views: List[DrawingView],
    ) -> Dict[int, List[str]]:
        members: Dict[int, List[str]] = {index: [] for index in range(len(views))}
        entity: SheetEntity
        for entity in entities:
            if not entity.is_top_level:
                continue
            owner: Optional[int] = self._owner_of(entity.boundary, views)
            if owner is not None:
                members[owner].append(entity.handle)
        return members

    def _owner_of(
        self,
        boundary: DrawingBoundary,
        views: List[DrawingView],
    ) -> Optional[int]:
        holders: List[int] = [
            index
            for index, view in enumerate(views)
            if view.boundary.contains(
                boundary, self.MARGIN_RATIO * view.boundary.diagonal
            )
        ]
        if not holders:
            return None
        return min(holders, key=lambda index: views[index].boundary.area)

    @staticmethod
    def _write_view(source: Drawing, handles: List[str], path: Path) -> None:
        target: Drawing = ezdxf.new(dxfversion=source.dxfversion)
        target.units = source.units
        importer: Importer = Importer(source, target)
        entities: List[DXFGraphic] = [source.entitydb[handle] for handle in handles]
        importer.import_entities(entities, target.modelspace())
        importer.finalize()
        target.saveas(str(path))
