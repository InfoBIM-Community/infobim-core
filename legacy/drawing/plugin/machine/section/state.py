from enum import Enum
from typing import Any, Dict


class IfcSectionProcessState(str, Enum):
    UNDEFINED = "__undefined__"
    IFC_LOADED = "__ifc_loaded__"
    REPRESENTATIONS_INSPECTED = "__representations_inspected__"
    NATIVE_PLAN_EXTRACTED = "__native_plan_extracted__"
    BODY_SECTION_GENERATED = "__body_section_generated__"
    DXF_WRITTEN = "__dxf_written__"

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
    def get_state(state: str) -> "IfcSectionProcessState":
        return getattr(IfcSectionProcessState, state.upper())

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
