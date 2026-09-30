from typing import Any

from stanza.models.common.doc import Document


class Pipeline:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __call__(self, text: str) -> Document:
        return Document(text)
