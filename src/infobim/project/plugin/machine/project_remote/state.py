from typing import Any, Dict

from infobim.project.plugin.machine.project_remote.port import ProjectRemoteProcessStatePort


class ProjectRemoteProcessState(ProjectRemoteProcessStatePort):
    """
    The states an InfoBIM remote project connection passes through.

    The OntoBDC remote container connection's own states are repeated here,
    in the order the connection reaches them, and the project states
    follow: the reserved dataset and the IfcProject it declares, set
    directly from the downloaded remote file, and the InfoBIM-specific
    refresh on top of it.
    """

    UNDEFINED = "__undefined__"
    REMOTE_FILE_AVAILABLE = "__remote_file_available__"
    REMOTE_CONTAINER_REACHABLE = "__remote_container_reachable__"
    STORAGE_ROOT_RECOVERED = "__storage_root_recovered__"
    TEMP_STORAGE_ROOT_INITIALIZED = "__temp_storage_root_initialized__"
    CONTAINER_CREATED = "__container_created__"
    CONTAINER_FILES_DOWNLOADED = "__container_files_downloaded__"
    CONTAINER_REFRESHED = "__container_refreshed__"
    PROJECT_SET = "__project_set__"
    PROJECT_REFRESHED = "__project_refreshed__"

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
    def get_state(state: str) -> "ProjectRemoteProcessState":
        return getattr(ProjectRemoteProcessState, state.upper())

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
