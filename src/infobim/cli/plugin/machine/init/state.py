from typing import Any, Dict

from infobim.cli.plugin.machine.init.port import InfoBIMInitProcessStatePort


class InfoBIMInitProcessState(InfoBIMInitProcessStatePort):
    """
    The states an initialized OntoBDC project goes through to become one an
    InfoBIM user can open. Labels and descriptions come from the statechart
    that declares them.
    """

    UNDEFINED = "__undefined__"
    SERVE_SHORTCUT_READY = "__serve_shortcut_ready__"

    def __init__(self, _: str) -> None:
        self._labels: Dict[str, str] = {}
        self._descriptions: Dict[str, str] = {}

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize(label)
        self._descriptions = self._normalize(description)

    def label(self, lang: str = "en") -> str:
        return self._localized(self._labels, lang, self.value)

    def description(self, lang: str = "en") -> str:
        return self._localized(self._descriptions, lang, "")

    @staticmethod
    def get_state(state: str) -> "InfoBIMInitProcessState":
        return getattr(InfoBIMInitProcessState, state.upper())

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
    def _localized(values: Dict[str, str], lang: str, default: str) -> str:
        normalized: str = lang.strip().lower().replace("_", "-")
        return values.get(normalized, values.get("en", default))
