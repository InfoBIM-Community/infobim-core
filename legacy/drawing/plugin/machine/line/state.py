from enum import Enum
from typing import Any, Dict


class DxfLineProcessState(str, Enum):
    UNDEFINED = "__undefined__"
    DXF_LOADED = "__dxf_loaded__"
    LINE_CAPTURED = "__line_captured__"
    TRACE_READY = "__trace_ready__"

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize(label)
        self._descriptions = self._normalize(description)

    def label(self, lang: str = "en") -> str:
        return self._localized(getattr(self, "_labels", {}), lang, self.value)

    def description(self, lang: str = "en") -> str:
        return self._localized(getattr(self, "_descriptions", {}), lang, "")

    @staticmethod
    def get_state(state: str) -> "DxfLineProcessState":
        return getattr(DxfLineProcessState, state.upper())

    @staticmethod
    def _normalize(value: Any) -> Dict[str, str]:
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
    def _localized(
        values: Dict[str, str],
        lang: str,
        default: str,
    ) -> str:
        normalized = lang.strip().lower().replace("_", "-")
        return values.get(normalized, values.get("en", default))
