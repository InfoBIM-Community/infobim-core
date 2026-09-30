from typing import Any, ClassVar, Dict

from infobim.dict.domain.port.machine import DictionaryEntityCreateProcessStatePort


class DictionaryEntityContextKeys:
    """
    The context keys this machine's states are read from and written to.

    Naming them here, rather than importing a capability into the
    evaluator or the evaluator into a capability, is what keeps the two
    sides of a state independent: the capability that brings a state about
    and the evaluator that reports it agree on a key and on nothing else.
    """

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    IFC_MODEL_PATH_KEY: ClassVar[str] = "ifc_model_path"
    # Not "global_id": that key is the Project's own selector, bound by
    # the parameter strategy that answers for --global-id, and an element
    # of the Project is not the Project.
    ELEMENT_GLOBAL_ID_KEY: ClassVar[str] = "element_global_id"
    TITLE_KEY: ClassVar[str] = "title"
    DICTIONARY_URI_KEY: ClassVar[str] = "dictionary_uri"
    DICTIONARY_NAMESPACE_KEY: ClassVar[str] = "dictionary_namespace"
    DICTIONARY_ENTRY_PATH_KEY: ClassVar[str] = "dictionary_entry_path"
    DICTIONARY_DEFINITION_KEY: ClassVar[str] = "dictionary_definition"
    POSITION_KEY: ClassVar[str] = "position"

    # The keys the IFC creation flow's own states are read from. They are
    # the same keys here because they are the same facts: from the shape
    # onwards, an element defined from a dictionary and one created by a
    # command are the same kind of thing, and the states they pass
    # through are shared rather than mirrored.
    GEOMETRY_KEY: ClassVar[str] = "geometry"
    GEOMETRY_ITEM_KEY: ClassVar[str] = "geometry_item"
    STEP_ELEMENTS_KEY: ClassVar[str] = "step_elements"
    SHAPE_REPRESENTATION_KEY: ClassVar[str] = "shape_representation"
    GEOMETRIC_PRODUCT_KEY: ClassVar[str] = "geometric_product"
    FEDERATED_PRODUCT_KEY: ClassVar[str] = "federated_product"


class DictionaryEntityCreateProcessState(DictionaryEntityCreateProcessStatePort):
    """
    The states defining an element from a dictionary passes through.

    ``IFC_MODEL_HEALTHY`` is a fact of the model, read by the same
    standalone checks every other IFC flow reads it with: the file on disk
    either is usable and agrees with the project, or is not, and the
    answer survives the process ending.

    ``POSITION_DEFINED`` is a fact of the run — where this invocation puts
    the element — and is read from the invocation itself, never written
    down as a flag that would claim, for every later run, that a value it
    no longer has was already decided.

    ``ELEMENT_IDENTIFIED`` is the identity of the element being defined.
    It is derived from the Project and the title by the Project's own
    rule, the same rule the IFC creation flow derives a product's
    identity by, so defining the same element again is the same element
    and its state is filed under it rather than under the name it
    happened to be called by.

    ``DICTIONARY_ENTRY_DOWNLOADED`` is the document the dictionary
    answered with, stored in the project's own state so the element can
    always be explained by what was read rather than by a URL that may
    since have changed. ``ENTITY_DEFINITION_READ`` is what that document
    declares, understood in the terms the entry used: the IFC class, the
    predefined type it is restricted to, the classes the element also
    belongs to, and the shape it is described by.

    From ``GEOMETRY_DEFINED`` on, the states are the IFC creation flow's
    own, and they are shared rather than mirrored. A shape completely
    defined, an IFC representation item carrying it, a shape
    representation wrapping that item, an element carrying the
    representation and a model carrying the element are the same five
    facts whether the measurements came from a command or from a
    dictionary, and the only two this domain answers for itself are the
    ones where the dictionary is the one speaking: the shape it
    describes, and the class and predefined type it says the element is.

    ``GEOMETRIC_PRODUCT_FEDERATED`` is the project's model carrying the
    element, measured in the model's own context and contained in the
    storey that holds it. Everything before it happens in the project's
    state, where an unfinished element harms nobody.
    """

    UNDEFINED = "__undefined__"
    IFC_MODEL_HEALTHY = "__ifc_model_healthy__"
    POSITION_DEFINED = "__position_defined__"
    ELEMENT_IDENTIFIED = "__element_identified__"
    DICTIONARY_ENTRY_DOWNLOADED = "__dictionary_entry_downloaded__"
    ENTITY_DEFINITION_READ = "__entity_definition_read__"
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
    def get_state(state: str) -> "DictionaryEntityCreateProcessState":
        return getattr(DictionaryEntityCreateProcessState, state.upper())

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
