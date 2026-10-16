from typing import Any, Dict

from infobim.context.plugin.machine.entity_inspection.port import EntityInspectionProcessStatePort


class EntityInspectionProcessState(EntityInspectionProcessStatePort):
    """The states of the InfoBIM entity inspection."""

    UNDEFINED = "__undefined__"
    ENTITY_URI_RESOLVED = "__entity_uri_resolved__"
    ENTITY_INFORMATION_FOUND = "__entity_information_found__"

    def __init__(self, _: str) -> None:
        self._labels: Dict[str, str] = {}
        self._descriptions: Dict[str, str] = {}

    def bind_presentation_metadata(self, label: Any = None, description: Any = None) -> None:
        self._labels = self._normalize_presentation_metadata(label)
        self._descriptions = self._normalize_presentation_metadata(description)

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(self._labels, lang, self.value)

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(self._descriptions, lang, "")

    @staticmethod
    def get_state(state: str) -> "EntityInspectionProcessState":
        return getattr(EntityInspectionProcessState, state.upper())

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
    def _localized_presentation_metadata(values: Dict[str, str], lang: str, default: str) -> str:
        normalized_lang = lang.strip().lower().replace("_", "-")
        return values.get(normalized_lang, values.get("en", default))
