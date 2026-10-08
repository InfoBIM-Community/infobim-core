from typing import Any, Dict

from infobim.project.plugin.machine.project_refresh.port import ProjectRefreshProcessStatePort


class ProjectRefreshProcessState(ProjectRefreshProcessStatePort):
    """
    The InfoBIM-specific states a project passes through after the OntoBDC
    container refresh finishes.

    The OntoBDC container refresh stage is driven entirely by the
    container's own state machine — its states are NOT repeated here,
    so the project refresh handler stays decoupled from any change in
    the container contract. The project-level handler is only asked to
    run AFTER the container handler reports success.
    """

    UNDEFINED = "__undefined__"
    PROJECT_DATASET_REFRESHED = "__project_dataset_refreshed__"
    IFC_PROJECT_REFRESHED = "__ifc_project_refreshed__"
    PROJECT_READY_TO_RENDER = "__project_ready_to_render__"

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
    def get_state(state: str) -> "ProjectRefreshProcessState":
        return getattr(ProjectRefreshProcessState, state.upper())

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
