import os
from typing import List


class Word:
    def __init__(self, text: str) -> None:
        self.text: str = text
        self.lemma: str = text.lower()
        self.upos: str = "NOUN"


class Sentence:
    def __init__(self, text: str) -> None:
        self.words: List[Word] = [Word(token) for token in text.split()]


class Document:
    def __init__(self, text: str) -> None:
        self.lang: str = os.environ["INFOBIM_E2E_STANZA_LANGUAGE"]
        self.sentences: List[Sentence] = [Sentence(text)]
