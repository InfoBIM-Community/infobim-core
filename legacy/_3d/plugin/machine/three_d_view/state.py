from typing import Any, ClassVar, Dict

from ....domain.port.machine import ThreeDViewProcessStatePort


class ThreeDViewProcessState(ThreeDViewProcessStatePort):
    """
    The states opening the InfoBIM 3D viewer for a Project passes through.

    Resolving and validating the Project itself is the command's own
    precondition, checked before this machine ever runs -- a Project that
    fails that is never a Project this machine is asked about. What this
    machine tracks is what the viewer page still needs prepared: the
    Project's own IfcProject, read fresh from ifc_project.ttl and staged
    as JSON-LD for every launch. There is no durable, on-disk fact of
    "already injected" the way the other machines in this codebase check
    for -- IFC_PROJECT_INJECTED is observed from this command's own
    in-memory context instead, true only once this run has actually
    staged it (see ThreeDViewStateEvaluatorAdapter).
    """

    UNDEFINED = "__undefined__"
    IFC_ELEMENT_MESHES_CONVERTED = "__ifc_element_meshes_converted__"
    IFC_PROJECT_INJECTED = "__ifc_project_injected__"
    PROJECT_TREE_INJECTED = "__project_tree_injected__"
    THREE_D_ELEMENT_TREE_INJECTED = "__three_d_element_tree_injected__"

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
    def get_state(state: str) -> "ThreeDViewProcessState":
        return getattr(ThreeDViewProcessState, state.upper())

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


class ThreeDViewContextKeys:
    """
    Context parameter keys this machine's states read and write.

    IfcProjectInjectedCapability sets IFC_PROJECT_JSONLD_KEY as its
    result; ProjectTreeInjectedCapability sets PROJECT_TREE_KEY the same
    way. ThreeDViewStateEvaluatorAdapter and ThreeDCommand both need
    these same keys to read them back. Naming them here, not on the
    capability classes, is what lets both of them do that without
    importing a concrete capability -- this machine's own vocabulary is
    a fact about the machine, not about the capability that happens to
    fill it in today.
    """

    IFC_ELEMENT_MESHES_KEY: ClassVar[str] = "ifc_element_meshes"
    IFC_PROJECT_JSONLD_KEY: ClassVar[str] = "ifc_project_jsonld"
    PROJECT_TREE_KEY: ClassVar[str] = "project_tree"
    THREE_D_ELEMENT_TREE_KEY: ClassVar[str] = "three_d_element_tree"
