from typing import Any, Dict

from infobim.ifc.domain.port.machine import GeometricProductCreateProcessStatePort


class GeometricProductCreateProcessState(GeometricProductCreateProcessStatePort):
    """
    The states creating a geometric product in an IFC model passes through.

    Two kinds of state live in this sequence, and the difference is
    deliberate. ``IFC_MODEL_HEALTHY``, ``UNIT_DEFINED``,
    ``GEOMETRY_CREATED`` and ``SHAPE_REPRESENTATION_CREATED`` are facts of
    the model: the file on disk either is usable, states its units, carries
    the geometry, carries the representation — or does not, and the answer
    survives the process ending.

    ``POSITION_DEFINED`` and ``GEOMETRY_DEFINED`` are facts of the run. A
    position and a primitive's dimensions are inputs this execution was
    given, and they are read from the execution itself; a process that
    starts again defines them again. Nothing writes them down as a flag,
    because a flag would claim, for every later run, that a value it no
    longer has was already decided.

    ``GEOMETRIC_PRODUCT_CREATED`` is the product itself: the IFC element
    the title names, carrying the representation as its own. It is
    assembled in a fragment of the project's state, not in the model the
    project federates.

    ``GEOMETRIC_PRODUCT_FEDERATED`` is that model carrying it: the
    element measured in the model's own context, placed in its spatial
    structure and contained in the storey that holds it. Everything
    before this state happens where an unfinished product harms nobody,
    which is the whole reason the two are separate.
    """

    UNDEFINED = "__undefined__"
    IFC_MODEL_HEALTHY = "__ifc_model_healthy__"
    UNIT_DEFINED = "__unit_defined__"
    POSITION_DEFINED = "__position_defined__"
    GEOMETRY_DEFINED = "__geometry_defined__"
    GEOMETRY_CREATED = "__geometry_created__"
    SHAPE_REPRESENTATION_CREATED = "__shape_representation_created__"
    GEOMETRIC_PRODUCT_CREATED = "__geometric_product_created__"
    GEOMETRIC_PRODUCT_FEDERATED = "__geometric_product_federated__"

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
    def get_state(state: str) -> "GeometricProductCreateProcessState":
        return getattr(GeometricProductCreateProcessState, state.upper())

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
