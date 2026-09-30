from ontobdc.cli.adapter.surface import (
    BorderlessTerminalSurfaceRenderer,
    TerminalSurfaceRenderer,
)
from ontobdc.cli.domain.port.renderer import TerminalSurfacePort
from ontobdc.shared.domain.port.component import TerminalTileRenderable

from infobim.cli.adapter.logo import InfoBIMOperationTile


class InfoBIMTerminalSurfaceAdapter(TerminalSurfacePort):
    """
    Renders a command response on the terminal under the InfoBIM brand.

    The surface assembly is OntoBDC's; this only says which tile the
    operation region carries, so the frame InfoBIM prints is the same frame
    with a different name on it.
    """

    def render(self, body_markdown: str, theme: str) -> str:
        operation_tile: TerminalTileRenderable = InfoBIMOperationTile()

        return TerminalSurfaceRenderer.with_content_surface(
            body_markdown,
            theme=theme,
            operation_tile=operation_tile,
        )


class BorderlessInfoBIMTerminalSurfaceAdapter(TerminalSurfacePort):
    """
    Renders a command response under the InfoBIM brand, without the outer
    box frame.

    Selected in place of InfoBIMTerminalSurfaceAdapter when the caller's
    real display width cannot be trusted -- see
    BorderlessTerminalSurfaceRenderer's own docstring for why that makes
    the framed box the wrong choice. with_content_surface is called on
    that subclass rather than on TerminalSurfaceRenderer for the same
    reason InfoBIMTerminalSurfaceAdapter calls it on the base class: the
    classmethod builds an instance of whichever class it was called on.
    """

    def render(self, body_markdown: str, theme: str) -> str:
        operation_tile: TerminalTileRenderable = InfoBIMOperationTile()

        return BorderlessTerminalSurfaceRenderer.with_content_surface(
            body_markdown,
            theme=theme,
            operation_tile=operation_tile,
        )
