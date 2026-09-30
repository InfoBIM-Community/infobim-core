from typing import Any, Dict

from infobim.project.plugin.machine.project_create.port import ProjectCreateProcessStatePort


class ProjectCreateProcessState(ProjectCreateProcessStatePort):
    """
    The states an InfoBIM project passes through while it is created.

    A project is an OntoBDC container that carries more, so the container's
    own creation states are repeated here, in the order the container
    reaches them, and the project states follow: the reserved dataset, and
    the IfcProject the model hangs from.
    """

    UNDEFINED = "__undefined__"
    INVALID_PATH = "__invalid_path__"
    DIRECTORY_READY = "__directory_ready__"
    CONTAINER_METADATA_READY = "__container_metadata_ready__"
    CONTAINER_STORAGE_INDEX_READY = "__container_storage_index_ready__"
    CONTAINER_MANIFEST_SYNCED = "__container_manifest_synced__"
    PROJECT_DATASET_READY = "__project_dataset_ready__"
    IFC_PROJECT_READY = "__ifc_project_ready__"

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
    def get_state(state: str) -> "ProjectCreateProcessState":
        return getattr(ProjectCreateProcessState, state.upper())

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
