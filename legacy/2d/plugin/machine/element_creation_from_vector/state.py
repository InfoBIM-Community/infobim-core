from enum import Enum
from typing import Any, Dict

from infobim.context.adapter.taxonomy import KIND_STATE, REPRESENTATION_STATE


class DxfVectorProcessState(str, Enum):
    UNDEFINED = "__undefined__"
    ELEMENT_KIND_RESOLVED = KIND_STATE
    ELEMENT_REPRESENTATION_RESOLVED = REPRESENTATION_STATE
    WORK_PLANE_CONFIRMED = "__work_plane_confirmed__"
    DXF_LOADED = "__dxf_loaded__"
    VECTOR_CAPTURED = "__vector_captured__"
    PIPE_RADIUS_DEFINED = "__pipe_radius_defined__"
    IFC_ELEMENT_CREATED = "__ifc_element_created__"
    TRACE_READY = "__trace_ready__"

    def __init__(self, value: str) -> None:
        self._labels: Dict[str, str] = {}
        self._descriptions: Dict[str, str] = {}

    def bind_presentation_metadata(
        self, label: Any = None, description: Any = None
    ) -> None:
        self._labels = self._normalize(label)
        self._descriptions = self._normalize(description)

    def label(self, lang: str = "en") -> str:
        return self._localized(self._labels, lang, self.value)

    def description(self, lang: str = "en") -> str:
        return self._localized(self._descriptions, lang, "")

    @staticmethod
    def get_state(state: str) -> "DxfVectorProcessState":
        return DxfVectorProcessState[state.upper()]

    @staticmethod
    def _normalize(value: Any) -> Dict[str, str]:
        if value is None:
            return {}
        if isinstance(value, str):
            return {"en": value}
        if not isinstance(value, dict):
            raise ValueError("State presentation metadata must be text or a language mapping.")
        result: Dict[str, str] = {}
        language: Any
        text: Any
        for language, text in value.items():
            if not isinstance(language, str) or not language.strip():
                raise ValueError("State metadata requires a non-empty language code.")
            if not isinstance(text, str):
                raise ValueError("State metadata requires text for every language.")
            result[language.strip().lower().replace("_", "-")] = text
        return result

    @staticmethod
    def _localized(values: Dict[str, str], lang: str, default: str) -> str:
        """Optional display metadata uses English, then the declared display default."""
        normalized: str = lang.strip().lower().replace("_", "-")
        if normalized in values:
            return values[normalized]
        if "en" in values:
            return values["en"]
        return default
