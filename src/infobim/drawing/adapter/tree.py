from typing import Any, ClassVar, Dict, List

from infobim.shared.adapter.tree import FileTree
from infobim.drawing.domain.model.view import DrawingView


class DrawingTree:
    """Build the drawing branch shown when inspecting a container."""

    ROOT_NAME_BY_LANGUAGE: ClassVar[Dict[str, str]] = {
        "en": "Drawings",
        "pt-br": "Pranchas e Desenhos",
    }
    DEFAULT_LANGUAGE: ClassVar[str] = "en"
    ROOT_KIND: ClassVar[str] = "drawing"
    DRAWING_KIND: ClassVar[str] = "drawing"

    @classmethod
    def of(cls, drawing_paths: List[str], lang: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
        return FileTree.of(
            file_paths=drawing_paths,
            root_name=cls._root_name_of(lang),
            root_kind=cls.ROOT_KIND,
            file_kind=cls.DRAWING_KIND,
        )

    @classmethod
    def _root_name_of(cls, lang: str) -> str:
        if lang in cls.ROOT_NAME_BY_LANGUAGE:
            return cls.ROOT_NAME_BY_LANGUAGE[lang]
        return cls.ROOT_NAME_BY_LANGUAGE[cls.DEFAULT_LANGUAGE]


class DrawingViewTree:
    """
    Build the tree of the Drawing Views discovered on one drawing.

    The drawing is the root and each view a leaf labelled with its title,
    its kind and, when known, its scale.
    """

    ROOT_KIND: ClassVar[str] = "drawing"
    VIEW_KIND: ClassVar[str] = "file"

    @classmethod
    def of(cls, drawing_name: str, views: List[DrawingView]) -> Dict[str, Any]:
        return {
            "name": drawing_name,
            "kind": cls.ROOT_KIND,
            "children": [
                {"name": cls.label(view), "kind": cls.VIEW_KIND, "children": []}
                for view in views
            ],
        }

    @staticmethod
    def label(view: DrawingView) -> str:
        label: str = f"{view.title} [{view.kind.value}]"
        if view.scale is None:
            return label
        return f"{label} {view.scale}"
