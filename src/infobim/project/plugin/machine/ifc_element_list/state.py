from typing import Any, Dict

from infobim.project.plugin.machine.ifc_element_list.port import IfcElementListProcessStatePort


class IfcElementListProcessState(IfcElementListProcessStatePort):
    """
    The states the listing of the IFC elements of a project passes through:
    first the IFC models the project holds are found, then their elements
    are read.
    """

    UNDEFINED = "__undefined__"
    IFC_MODELS_FOUND = "__ifc_models_found__"
    IFC_ELEMENTS_READ = "__ifc_elements_read__"

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
    def get_state(state: str) -> "IfcElementListProcessState":
        return getattr(IfcElementListProcessState, state.upper())

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
