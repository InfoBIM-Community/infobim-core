from enum import Enum
from typing import Any, ClassVar, Dict


class IfcImportContextKeys:
    IMPORT_PATH_KEY: ClassVar[str] = "import_path"
    KIND_KEY: ClassVar[str] = "ifc_kind"
    DXF_SOURCE_KEY: ClassVar[str] = "dxf_source"
    REPRESENTATION_KIND_KEY: ClassVar[str] = "representation_kind"
    DXF_GEOMETRY_KEY: ClassVar[str] = "dxf_geometry"
    IMPORT_READY_KEY: ClassVar[str] = "import_ready"


class IfcImportProcessState(str, Enum):
    UNDEFINED = "__undefined__"
    DXF_SOURCE_READY = "__dxf_source_ready__"
    REPRESENTATION_KIND_DEFINED = "__representation_kind_defined__"
    DXF_GEOMETRY_READ = "__dxf_geometry_read__"
    IMPORT_READY = "__import_ready__"

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
    def get_state(state: str) -> "IfcImportProcessState":
        return getattr(IfcImportProcessState, state.upper())

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
        normalized_lang = lang.strip().lower().replace("_", "-")
        return values.get(normalized_lang, values.get("en", default))
