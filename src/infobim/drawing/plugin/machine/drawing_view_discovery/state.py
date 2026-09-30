from typing import Any, Dict

from infobim.drawing.plugin.machine.drawing_view_discovery.port import (
    DrawingViewDiscoveryProcessStatePort,
)


class DrawingViewDiscoveryState(DrawingViewDiscoveryProcessStatePort):
    """
    The states the discovery of the Drawing Views of a sheet passes through.

    The discovery strategies run from the most explicit evidence to the
    most heuristic one, each refining the same candidate collection:
    viewports, titles and scales, frames, graphic references, and spatial
    clusters for what none of them delimited. Views are classified only
    once they are delimited, and then extracted into DXFs of their own.

    ``DRAWING_VIEW_RELATIONSHIPS_MODELED`` is reached once the sheet and
    its views are modelled as ICDD documents and links and as OntoSTEP
    presentation entities, and that model conforms to the canonical SHACL
    shapes.
    """

    UNDEFINED = "__undefined__"
    DRAWING_VIEWPORTS_DISCOVERED = "__drawing_viewports_discovered__"
    DRAWING_VIEW_TITLES_RESOLVED = "__drawing_view_titles_resolved__"
    DRAWING_VIEW_FRAMES_DETECTED = "__drawing_view_frames_detected__"
    DRAWING_VIEW_REFERENCES_DETECTED = "__drawing_view_references_detected__"
    DRAWING_VIEW_CLUSTERS_DETECTED = "__drawing_view_clusters_detected__"
    DRAWING_VIEWS_CLASSIFIED = "__drawing_views_classified__"
    DRAWING_VIEWS_EXTRACTED = "__drawing_views_extracted__"
    DRAWING_VIEW_RELATIONSHIPS_MODELED = "__drawing_view_relationships_modeled__"

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize_presentation_metadata(label)
        self._descriptions = self._normalize_presentation_metadata(description)

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_labels", {}),
            lang=lang,
            default=self.value,
        )

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_descriptions", {}),
            lang=lang,
            default="",
        )

    @staticmethod
    def get_state(state: str) -> "DrawingViewDiscoveryState":
        return getattr(DrawingViewDiscoveryState, state.upper())

    @staticmethod
    def _normalize_presentation_metadata(value: Any) -> Dict[str, str]:
        if isinstance(value, str):
            return {"en": value}
        if not isinstance(value, dict):
            return {}

        return {
            str(language).strip().lower().replace("_", "-"): str(text)
            for language, text in value.items()
            if str(language).strip() and text is not None
        }

    @staticmethod
    def _localized_presentation_metadata(
        values: Dict[str, str],
        lang: str,
        default: str,
    ) -> str:
        normalized_lang: str = lang.strip().lower().replace("_", "-")
        return values.get(normalized_lang, values.get("en", default))
