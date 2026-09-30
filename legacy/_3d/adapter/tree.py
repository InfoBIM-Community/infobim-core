from typing import Any, ClassVar, Dict, List


class ThreeDElementTree:
    """
    Lists renderable 3D elements as the direct children of a single root.

    Unlike drawings, a renderable element's own folder structure (the ETL
    pipeline's internal cache layout, e.g. `.__infobim__/payload/document
    /etl/format/dxf/ifcx/`) says nothing a reader is looking for -- so,
    unlike `DrawingTree`, this does not fold paths back into the
    directories they sit in. Every element is listed flat, directly under
    the root.

    An element carries both its title (a human name, recovered from its
    header when its own file name is a content hash) and its file name.
    Only the title becomes the node's displayed "name" -- TreeWidget
    renders "name"/"kind"/"children" and ignores any other key, so the
    file name (and, when supplied, the element's own parsed document --
    see DOCUMENT_KEY) travels in the node for a JSON reader without ever
    reaching the terminal render.
    """

    ROOT_NAME_BY_LANGUAGE: ClassVar[Dict[str, str]] = {
        "en": "3D Elements",
        "pt-br": "Elementos 3D",
    }
    DEFAULT_LANGUAGE: ClassVar[str] = "en"
    ROOT_KIND: ClassVar[str] = "model"
    ELEMENT_KIND: ClassVar[str] = "model"

    NAME_KEY: ClassVar[str] = "name"
    KIND_KEY: ClassVar[str] = "kind"
    CHILDREN_KEY: ClassVar[str] = "children"
    TITLE_KEY: ClassVar[str] = "title"
    FILE_NAME_KEY: ClassVar[str] = "file_name"
    DOCUMENT_KEY: ClassVar[str] = "document"

    @classmethod
    def of(cls, elements: List[Dict[str, Any]], lang: str = "en") -> Dict[str, Any]:
        """
        Return the given elements as a flat list under one root.

        Each element is a mapping with at least TITLE_KEY and
        FILE_NAME_KEY. Any other key (e.g. DOCUMENT_KEY, for the
        offline viewer's "3D inspect" tab) rides through onto the node
        unchanged, so a caller that needs more than the CLI does is
        never blocked from adding it.
        """
        ordered_elements: List[Dict[str, Any]] = sorted(
            elements, key=lambda element: element[cls.TITLE_KEY].lower()
        )

        return {
            cls.NAME_KEY: cls._root_name_of(lang),
            cls.KIND_KEY: cls.ROOT_KIND,
            cls.CHILDREN_KEY: [
                {
                    cls.NAME_KEY: element[cls.TITLE_KEY],
                    cls.KIND_KEY: cls.ELEMENT_KIND,
                    cls.CHILDREN_KEY: [],
                    **{
                        key: value
                        for key, value in element.items()
                        if key != cls.TITLE_KEY
                    },
                }
                for element in ordered_elements
            ],
        }

    @classmethod
    def _root_name_of(cls, lang: str) -> str:
        """
        Return the root's display name in the given language, English otherwise.
        """
        return cls.ROOT_NAME_BY_LANGUAGE.get(
            lang, cls.ROOT_NAME_BY_LANGUAGE[cls.DEFAULT_LANGUAGE]
        )
