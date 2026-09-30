from typing import Any, Dict

from infobim.ifc.plugin.machine.geometric_product_delete.port import GeometricProductDeleteProcessStatePort


class GeometricProductDeleteProcessState(GeometricProductDeleteProcessStatePort):
    """
    The states deleting a geometric product from an IFC model passes through.

    ``IFC_MODEL_HEALTHY`` and ``GLOBAL_ID_KNOWN`` are prerequisites of the
    deletion itself: the file on disk must be usable, and the element to
    remove must be an IFC product actually carried by it.

    ``GLOBAL_ID_PRESENT`` is a fact of the model: an element under the
    requested GlobalId exists in the federated model. Removing it is the
    step after, because existence is a prerequisite to removal rather than
    the removal itself.

    ``GEOMETRIC_PRODUCT_DEFEDERATED`` means the element and everything
    only it owned — its representation, the geometry that representation
    wraps, its placement and its spatial containment — are gone from the
    model. The model's own contexts and the storey it was placed in stay.

    ``STATE_CLEANED_UP`` means the assembled state that produced this
    product — the STEP files the creation flow wrote under the product's
    identity — is also gone from the project's ETL workspace.
    """

    UNDEFINED = "__undefined__"
    IFC_MODEL_HEALTHY = "__ifc_model_healthy__"
    GLOBAL_ID_KNOWN = "__global_id_known__"
    GLOBAL_ID_PRESENT = "__global_id_present__"
    GEOMETRIC_PRODUCT_DEFEDERATED = "__geometric_product_defederated__"
    STATE_CLEANED_UP = "__state_cleaned_up__"

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
    def get_state(state: str) -> "GeometricProductDeleteProcessState":
        return getattr(GeometricProductDeleteProcessState, state.upper())

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
