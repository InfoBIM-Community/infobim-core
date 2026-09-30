from io import BytesIO
from typing import ClassVar, List, Tuple

from PIL import Image, ImageFilter
from rich.text import Text
from rich.style import Style


class BraillePreview:
    """
    Draw a line-drawing preview in braille characters, fitted to a pane.

    Each character holds a 2 × 4 grid of dots, four times the dots of half
    blocks, which is what thin CAD lines need to stay visible in a
    terminal. The image is reduced in two steps that keep the lines: dark
    strokes are first thickened by about the reduction factor, so that
    shrinking cannot fade a one-pixel line into the background, and every
    reduced pixel is then either ink or paper.
    """

    DOTS_WIDE: ClassVar[int] = 2
    DOTS_HIGH: ClassVar[int] = 4
    INK_THRESHOLD: ClassVar[int] = 200
    BLANK: ClassVar[int] = 0x2800
    # Bit of each dot of a braille cell, indexed by [row][column].
    DOT_BITS: ClassVar[Tuple[Tuple[int, int], ...]] = (
        (0x01, 0x08),
        (0x02, 0x10),
        (0x04, 0x20),
        (0x40, 0x80),
    )
    STYLE: ClassVar[Style] = Style(color="black", bgcolor="white")

    @classmethod
    def of(cls, rendered: bytes, columns: int, rows: int) -> Text:
        ink: Image.Image = cls._ink(rendered, columns, rows)
        width: int = ink.width
        height: int = ink.height
        pixels: List[int] = list(ink.getdata())
        lines: List[str] = []
        top: int
        for top in range(0, height, cls.DOTS_HIGH):
            cells: List[str] = []
            left: int
            for left in range(0, width, cls.DOTS_WIDE):
                cells.append(chr(cls.BLANK + cls._bits(pixels, width, height, left, top)))
            lines.append("".join(cells))
        return Text("\n".join(lines), style=cls.STYLE, no_wrap=True)

    @classmethod
    def _ink(cls, rendered: bytes, columns: int, rows: int) -> Image.Image:
        image: Image.Image = Image.open(BytesIO(rendered)).convert("L")
        box: Tuple[int, int] = (
            max(columns, 1) * cls.DOTS_WIDE,
            max(rows, 1) * cls.DOTS_HIGH,
        )
        reduction: float = max(image.width / box[0], image.height / box[1], 1.0)
        thickness: int = int(reduction) | 1
        if thickness > 1:
            image = image.filter(ImageFilter.MinFilter(thickness))
        image.thumbnail(box, Image.Resampling.LANCZOS)
        return image.point(lambda value: 255 if value < cls.INK_THRESHOLD else 0)

    @classmethod
    def _bits(
        cls, pixels: List[int], width: int, height: int, left: int, top: int
    ) -> int:
        bits: int = 0
        row: int
        for row in range(cls.DOTS_HIGH):
            column: int
            for column in range(cls.DOTS_WIDE):
                x: int = left + column
                y: int = top + row
                if x < width and y < height and pixels[y * width + x]:
                    bits |= cls.DOT_BITS[row][column]
        return bits
