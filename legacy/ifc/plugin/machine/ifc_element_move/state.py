from typing import Any, ClassVar, Dict

from infobim.ifc.domain.port.machine import IfcElementMoveProcessStatePort


class IfcElementMoveContextKeys:
    """
    The context keys this machine's states are read from and written to.

    Naming them here, rather than importing a capability into the
    evaluator or the evaluator into a capability, is what keeps the two
    sides of a state independent: the capability that brings a state
    about and the evaluator that reports it agree on a key and on
    nothing else.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    TITLE_KEY: ClassVar[str] = "title"
    AXIS_KEY: ClassVar[str] = "axis"
    AMOUNT_KEY: ClassVar[str] = "amount"
    ELEMENT_GLOBAL_ID_KEY: ClassVar[str] = "element_global_id"
    DISPLACEMENT_KEY: ClassVar[str] = "displacement"
    MOVED_POSITION_KEY: ClassVar[str] = "moved_position"


class IfcElementMoveProcessState(IfcElementMoveProcessStatePort):
    """
    The states moving an existing element along one axis passes through.

    ``IFC_MODEL_HEALTHY`` is a fact of the model, read by the same
    standalone checks every other IFC flow reads it with: the file on
    disk either is usable and agrees with the project, or is not, and the
    answer survives the process ending.

    ``ELEMENT_LOCATED`` is the identity of the element this run moves,
    derived from the Project and the title by the Project's own rule —
    the same rule the IFC creation flow derives a product's identity by
    — and confirmed against the target model: a title nothing was ever
    created under names no element this flow may displace.

    ``DISPLACEMENT_DEFINED`` is a fact of the run: the axis and the
    amount this invocation names, turned into a vector with a value on
    one axis and zero on the other two. It is read from the invocation
    itself, never written down as a flag that would claim, for every
    later run, that a displacement it no longer has was already decided.

    ``ELEMENT_MOVED`` is the element's own placement carrying the new
    coordinate: the point every measurement of its representation is
    taken from, moved by exactly the vector this run defined.
    """

    UNDEFINED = "__undefined__"
    IFC_MODEL_HEALTHY = "__ifc_model_healthy__"
    ELEMENT_LOCATED = "__element_located__"
    DISPLACEMENT_DEFINED = "__displacement_defined__"
    ELEMENT_MOVED = "__element_moved__"

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
    def get_state(state: str) -> "IfcElementMoveProcessState":
        return getattr(IfcElementMoveProcessState, state.upper())

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
