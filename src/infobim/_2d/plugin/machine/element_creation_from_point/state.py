from typing import Any, Dict

from infobim._2d.plugin.machine.element_creation_from_point.port import (
    ElementCreationFromPointProcessStatePort,
)


class ElementCreationFromPointProcessState(ElementCreationFromPointProcessStatePort):
    """
    The states an element passes through while it is created from points
    picked on a drawing, starting from the text that names its kind.
    """

    UNDEFINED = "__undefined__"
    TEXT_NORMALIZED = "__text_normalized__"
    TEXT_LANGUAGE_IDENTIFIED = "__text_language_identified__"
    TEXT_LEMMATIZED = "__text_lemmatized__"
    ONTOLOGY_TERM_RESOLVED = "__ontology_term_resolved__"
    KIND_REPRESENTATION_RESOLVED = "__kind_representation_resolved__"
    FILE_METADATA_EXTRACTED = "__file_metadata_extracted__"
    DRAWING_DOCUMENTS_LOADED = "__drawing_documents_loaded__"
    DXF_VIEWER_OPENED = "__dxf_viewer_opened__"
    POINTS_CAPTURED = "__points_captured__"
    IFC_ELEMENTS_CREATED = "__ifc_elements_created__"

    def __init__(self, _: str) -> None:
        self._labels: Dict[str, str] = {}
        self._descriptions: Dict[str, str] = {}

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize_presentation_metadata(label)
        self._descriptions = self._normalize_presentation_metadata(description)

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=self._labels,
            lang=lang,
            default=self.value,
        )

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=self._descriptions,
            lang=lang,
            default="",
        )

    @staticmethod
    def get_state(state: str) -> "ElementCreationFromPointProcessState":
        return getattr(ElementCreationFromPointProcessState, state.upper())

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
