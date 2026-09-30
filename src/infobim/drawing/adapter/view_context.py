from typing import Any, Dict, List

from ezdxf.document import Drawing

from ontobdc.cli.domain.port.context import CliContextPort

from infobim.drawing.adapter.taxonomy import DrawingViewContextKeys
from infobim.drawing.domain.model.view import DrawingView
from infobim.drawing.domain.model.sheet import SheetEntity
from infobim.drawing.domain.model.view_candidates import DrawingViewCandidates


class DrawingViewContext:
    """
    Read, with their types checked, the values the discovery states share.

    A value that is missing or of another type means an earlier state did
    not run, and is reported as such instead of being guessed.
    """

    @classmethod
    def document(cls, context: CliContextPort) -> Drawing:
        documents: Any = cls._value(context, DrawingViewContextKeys.DXF_DOCUMENTS)
        if not isinstance(documents, dict):
            raise ValueError("The DXF documents in the context are not a mapping.")
        typed: Dict[str, Any] = documents
        if DrawingViewContextKeys.DXF_ORIGINAL not in typed:
            raise ValueError("The context carries no original DXF document.")
        document: Any = typed[DrawingViewContextKeys.DXF_ORIGINAL]
        if not isinstance(document, Drawing):
            raise ValueError("The original DXF document is not an ezdxf drawing.")
        return document

    @classmethod
    def entities(cls, context: CliContextPort) -> List[SheetEntity]:
        entities: Any = cls._value(context, DrawingViewContextKeys.SHEET_ENTITIES)
        if not isinstance(entities, list) or not all(
            isinstance(entity, SheetEntity) for entity in entities
        ):
            raise ValueError("The sheet entities in the context are not SheetEntity.")
        return entities

    @classmethod
    def candidates(cls, context: CliContextPort) -> DrawingViewCandidates:
        candidates: Any = cls._value(context, DrawingViewContextKeys.CANDIDATES)
        if not isinstance(candidates, DrawingViewCandidates):
            raise ValueError("The Drawing View candidates in the context are invalid.")
        return candidates

    @classmethod
    def views(cls, context: CliContextPort) -> List[DrawingView]:
        views: Any = cls._value(context, DrawingViewContextKeys.VIEWS)
        if not isinstance(views, list) or not all(
            isinstance(view, DrawingView) for view in views
        ):
            raise ValueError("The Drawing Views in the context are not DrawingView.")
        return views

    @staticmethod
    def _value(context: CliContextPort, key: str) -> Any:
        if not context.has_parameter(key):
            raise ValueError(f"The context carries no '{key}' yet.")
        return context.get_parameter_value(key)
