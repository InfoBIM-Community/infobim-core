import colorsys
import re
import shutil
from importlib import metadata
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image
from pyfiglet import Figlet


class LogoRenderAdapter:
    _RESET = "\x1b[0m"
    _BRAILLE_BASE = 0x2800
    _ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")
    _BRAILLE_DOTS = (
        (0, 0, 0x01),
        (0, 1, 0x02),
        (0, 2, 0x04),
        (1, 0, 0x08),
        (1, 1, 0x10),
        (1, 2, 0x20),
        (0, 3, 0x40),
        (1, 3, 0x80),
    )
    _TEXT_GAP = "  "
    _TEXT_INFO_VALUE = "Info"
    _TEXT_BIM_VALUE = "BIM"
    _TEXT_FONT = "standard"
    _VERSION_GAP = "  "
    _SLOGAN_GRAY = (148, 148, 148)
    _SLOGAN_LINES = [
        "",
        ">> A modular runtime environment for Engineering Automation <<",
    ]
    _BIM_BLUE = (25, 70, 109)
    _LOGO_SATURATION_FACTOR = 1.35
    _LOGO_VALUE_FACTOR = 1.2

    def __init__(self, image_path: Optional[Path] = None, width: int = 20, alpha_threshold: int = 32) -> None:
        self._image_path = image_path or self._resolve_logo_path()
        self._width = width
        self._alpha_threshold = alpha_threshold

    def render(self) -> str:
        logo_lines: List[str] = self._render_logo_lines()
        text_lines: List[str] = self._render_text_lines()
        merged_banner: str = self._merge_lines(logo_lines, text_lines)
        return self._center_banner(merged_banner)

    def bim_rgb(self) -> Tuple[int, int, int]:
        return self._enhance_logo_color(self._BIM_BLUE)

    def logo_width(self) -> int:
        logo_lines: List[str] = self._render_logo_lines()
        return max((self._visible_length(line) for line in logo_lines), default=self._width)

    def _render_logo_lines(self) -> List[str]:
        with Image.open(self._image_path) as source_image:
            img = source_image.convert("RGBA")

        bbox = img.getchannel("A").getbbox()
        if bbox is not None:
            img = img.crop(bbox)
        img = self._resize_for_braille_terminal(img, self._width)
        pixels = img.load()
        lines: List[str] = []

        for y in range(0, img.height, 4):
            line: List[str] = []
            for x in range(0, img.width, 2):
                cell_pixels: List[Tuple[int, int, int, int]] = [
                    pixels[x + dx, y + dy]
                    for dy in range(4)
                    for dx in range(2)
                ]
                char, color = self._braille_char(cell_pixels)
                if color is None:
                    line.append(" ")
                else:
                    line.append(f"{self._ansi_fg(color)}{char}")

            lines.append("".join(line).rstrip() + self._RESET)

        return lines

    def _render_text_lines(self) -> List[str]:
        figlet: Figlet = Figlet(font=self._TEXT_FONT)
        info_lines: List[str] = figlet.renderText(self._TEXT_INFO_VALUE).rstrip("\n").splitlines()
        bim_lines: List[str] = figlet.renderText(self._TEXT_BIM_VALUE).rstrip("\n").splitlines()
        bim_color: Tuple[int, int, int] = self._enhance_logo_color(self._BIM_BLUE)
        bim_lines_with_version: List[str] = self._append_version_to_bim_lines(bim_lines)
        total_lines: int = max(len(info_lines), len(bim_lines))
        normalized_info_lines: List[str] = self._normalize_lines(info_lines, total_lines)
        normalized_bim_lines: List[str] = self._normalize_lines(bim_lines_with_version, total_lines)
        merged_text_lines: List[str] = []

        for info_line, bim_line in zip(normalized_info_lines, normalized_bim_lines):
            if bim_line:
                merged_text_lines.append(f"{info_line}{self._ansi_fg(bim_color)}{bim_line}{self._RESET}")
                continue

            merged_text_lines.append(info_line)

        merged_text_lines.extend(self._render_slogan_lines())
        return merged_text_lines

    def _append_version_to_bim_lines(self, bim_lines: List[str]) -> List[str]:
        if not bim_lines:
            return []

        version_label: str = self._version_label()
        version_line_index: int = self._last_non_empty_line_index(bim_lines)
        updated_lines: List[str] = []

        for line_index, bim_line in enumerate(bim_lines):
            if line_index == version_line_index:
                updated_lines.append(f"{bim_line}{self._VERSION_GAP}{version_label}")
                continue

            updated_lines.append(bim_line)

        return updated_lines

    def _last_non_empty_line_index(self, lines: List[str]) -> int:
        for line_index in range(len(lines) - 1, -1, -1):
            if lines[line_index].strip():
                return line_index

        return max(len(lines) - 1, 0)

    def _render_slogan_lines(self) -> List[str]:
        rendered_lines: List[str] = []

        for slogan_line in self._SLOGAN_LINES:
            if not slogan_line:
                rendered_lines.append("")
                continue

            rendered_lines.append(f"{self._ansi_fg(self._SLOGAN_GRAY)}{slogan_line}{self._RESET}")

        return rendered_lines

    def _merge_lines(self, left_lines: List[str], right_lines: List[str]) -> str:
        total_lines: int = max(len(left_lines), len(right_lines))
        left_width: int = max((self._visible_length(line) for line in left_lines), default=0)
        normalized_left: List[str] = self._normalize_lines(left_lines, total_lines)
        normalized_right: List[str] = self._normalize_lines(right_lines, total_lines)
        merged_lines: List[str] = []

        for left_line, right_line in zip(normalized_left, normalized_right):
            padded_left_line: str = self._pad_ansi_line(left_line, left_width)
            merged_lines.append(f"{padded_left_line}{self._TEXT_GAP}{right_line}".rstrip())

        return "\n".join(merged_lines).strip()

    def _center_banner(self, banner: str) -> str:
        banner_lines: List[str] = banner.splitlines()
        banner_width: int = max((self._visible_length(line) for line in banner_lines), default=0)
        terminal_width: int = shutil.get_terminal_size(fallback=(banner_width, 40)).columns
        left_padding: int = max((terminal_width - banner_width) // 2, 0)
        padding: str = " " * left_padding

        return "\n".join(
            f"{padding}{line}" if line else ""
            for line in banner_lines
        )

    def _normalize_lines(self, lines: List[str], total_lines: int) -> List[str]:
        padding: int = max(total_lines - len(lines), 0)
        top_padding: int = padding // 2
        bottom_padding: int = padding - top_padding
        return ([""] * top_padding) + lines + ([""] * bottom_padding)

    def _pad_ansi_line(self, line: str, width: int) -> str:
        padding: int = max(width - self._visible_length(line), 0)
        return f"{line}{' ' * padding}"

    def _visible_length(self, value: str) -> int:
        return len(self._ANSI_PATTERN.sub("", value))

    def _resolve_logo_path(self) -> Path:
        return Path(__file__).resolve().parent / "asset" / "logo.png"

    def _resize_for_braille_terminal(self, img: Image.Image, term_width: int) -> Image.Image:
        aspect_ratio = img.height / img.width
        pixel_width = max(2, term_width * 2)
        pixel_height = max(4, int(round(pixel_width * aspect_ratio)))
        remainder = pixel_height % 4

        if remainder != 0:
            pixel_height += 4 - remainder

        return img.resize((pixel_width, pixel_height), Image.Resampling.LANCZOS)

    def _braille_char(
        self,
        cell_pixels: List[Tuple[int, int, int, int]],
    ) -> Tuple[str, Optional[Tuple[int, int, int]]]:
        mask: int = 0
        colors: List[Tuple[int, int, int]] = []

        for dx, dy, dot in self._BRAILLE_DOTS:
            pixel = cell_pixels[dy * 2 + dx]
            if pixel[3] <= self._alpha_threshold:
                continue

            mask |= dot
            colors.append(pixel[:3])

        if mask == 0:
            return " ", None

        avg_red: int = int(round(sum(color[0] for color in colors) / len(colors)))
        avg_green: int = int(round(sum(color[1] for color in colors) / len(colors)))
        avg_blue: int = int(round(sum(color[2] for color in colors) / len(colors)))
        avg_color: Tuple[int, int, int] = self._enhance_logo_color((avg_red, avg_green, avg_blue))
        return chr(self._BRAILLE_BASE + mask), avg_color

    def _ansi_fg(self, rgb: Tuple[int, int, int]) -> str:
        return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"

    def _enhance_logo_color(self, rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
        red: float = rgb[0] / 255
        green: float = rgb[1] / 255
        blue: float = rgb[2] / 255
        hue: float
        saturation: float
        value: float
        hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
        boosted_saturation: float = min(1.0, saturation * self._LOGO_SATURATION_FACTOR)
        boosted_value: float = min(1.0, value * self._LOGO_VALUE_FACTOR)
        enhanced_red: float
        enhanced_green: float
        enhanced_blue: float
        enhanced_red, enhanced_green, enhanced_blue = colorsys.hsv_to_rgb(hue, boosted_saturation, boosted_value)
        return (
            int(round(enhanced_red * 255)),
            int(round(enhanced_green * 255)),
            int(round(enhanced_blue * 255)),
        )

    def _version_label(self) -> str:
        return f"v{metadata.version('infobim')}"
