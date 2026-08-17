"""InfoBIM terminal logo.

Reuses OntoBDC's `LogoComponent` rendering machinery verbatim (ANSI
coloring, the compact one-line default vs. the large pyfiglet banner,
terminal-width centering) -- only the brand text and version lookup are
InfoBIM's own. This mirrors the exact relationship every other InfoBIM
command has with OntoBDC's CLI response/Widget/Surface stack: reuse, don't
reinvent.
"""

from importlib import metadata
from typing import Optional

from ontobdc.view.component.logo.python import LogoComponent


class InfoBIMLogoComponent(LogoComponent):
    """Terminal representation of the InfoBIM logo component."""

    PRIMARY_TEXT = "Info"
    ACCENT_TEXT = "BIM"
    TEXT_VALUE = PRIMARY_TEXT + ACCENT_TEXT

    def _version_label(self) -> str:
        version: Optional[str] = self._version
        if version is None:
            try:
                version = metadata.version("infobim")
            except metadata.PackageNotFoundError:
                version = None

        if not version:
            return ""
        return version if str(version).startswith("v") else f"v{version}"
