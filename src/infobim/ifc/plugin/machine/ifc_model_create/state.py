from typing import Any, Dict

from infobim.ifc.plugin.machine.ifc_model_create.port import IfcModelCreateProcessStatePort


class IfcModelCreateProcessState(IfcModelCreateProcessStatePort):
    """
    The states creating the IFC model file of a project passes through.

    ``IFC_MODEL_FILE_CREATED`` is a fact of the disk: a file is at the path
    the run names for the model, carrying the project's IfcProject.

    ``IFC_MODEL_DECLARED`` is a fact of the project: its RO-Crate states
    that file, which is what makes it a model other steps may write into.
    """

    UNDEFINED = "__undefined__"
    IFC_MODEL_FILE_CREATED = "__ifc_model_file_created__"
    IFC_MODEL_DECLARED = "__ifc_model_declared__"

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize_presentation_metadata(label)
        self._descriptions = self._normalize_presentation_metadata(description)

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_labels", {}),
            lang=lang,
            default=self.value,
        )

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_descriptions", {}),
            lang=lang,
            default="",
        )

    @staticmethod
    def get_state(state: str) -> "IfcModelCreateProcessState":
        return getattr(IfcModelCreateProcessState, state.upper())

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
