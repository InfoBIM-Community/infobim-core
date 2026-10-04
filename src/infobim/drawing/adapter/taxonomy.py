import re
from typing import ClassVar, List, Optional, Pattern, Tuple
import unicodedata

from rdflib import Namespace

from infobim.drawing.domain.model.view import DrawingViewKind


class DrawingViewContextKeys:
    """Context keys the Drawing View discovery states share."""

    DRAWING_PATH: ClassVar[str] = "file_open_path"
    DXF_DOCUMENTS: ClassVar[str] = "dxf_documents"
    DXF_ORIGINAL: ClassVar[str] = "dxf_original"
    SHEET_ENTITIES: ClassVar[str] = "drawing_sheet_entities"
    CANDIDATES: ClassVar[str] = "drawing_view_candidates"
    VIEWS: ClassVar[str] = "drawing_views"
    VIEWS_DIRECTORY: ClassVar[str] = "drawing_views_directory"
    CONTAINER_PATH: ClassVar[str] = "container_path"
    DRAWING_SOURCE_PATH: ClassVar[str] = "drawing_source_path"
    RELATIONSHIPS: ClassVar[str] = "drawing_view_relationships"


class DrawingViewNamespaces:
    """
    The vocabularies a sheet and its views are modelled with.

    ICDD (ISO 21597-1) declares the documents and links them; OntoSTEP /
    STP2OWL gives the sheet and its views their STEP presentation meaning.
    No canonical STP2OWL namespace for AP242 is available yet, so the STEP
    one is the provisional namespace the canonical SHACL shapes use; both
    must change together.
    """

    CT: ClassVar[Namespace] = Namespace(
        "https://standards.iso.org/iso/21597/-1/ed-1/en/Container#"
    )
    LS: ClassVar[Namespace] = Namespace(
        "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#"
    )
    STEP: ClassVar[Namespace] = Namespace("https://example.org/stp2owl/ap242#")
    SHAPES_IRI: ClassVar[str] = "http://datacenter.app.br/ontology/domain/aeco/tool/shacl.ttl"


class DrawingViewVocabulary:
    """
    The words that name, scale and reference Drawing Views on a sheet.

    Every list here is data, matched against text read with accents removed
    and in upper case, so a new term or language is one more entry rather
    than a change to the strategies that read them.
    """

    TITLE_PATTERNS: ClassVar[List[Tuple[Pattern[str], DrawingViewKind]]] = [
        (
            re.compile(r"^(PLANTA|PLAN\b|FLOOR PLAN|SITE PLAN|IMPLANTACAO|LOCACAO)"),
            DrawingViewKind.PLAN_VIEW,
        ),
        (
            re.compile(r"^(CORTE|SECAO|SECCAO|SECTION)\b"),
            DrawingViewKind.SECTION_VIEW,
        ),
        (
            re.compile(r"^(ELEVACAO|FACHADA|ELEVATION|VISTA)\b"),
            DrawingViewKind.ELEVATION_VIEW,
        ),
        (
            re.compile(r"^(DETALHE|DET\.|DETAIL|AMPLIACAO)"),
            DrawingViewKind.DETAIL_VIEW,
        ),
    ]
    SCALE_IN_TEXT: ClassVar[Pattern[str]] = re.compile(
        r"(?:ESC(?:ALA)?\.?|SCALE)\s*:?\s*(1\s*[:/]\s*\d+(?:[.,]\d+)?)"
    )
    SCALE_ONLY: ClassVar[Pattern[str]] = re.compile(
        r"^(?:(?:ESC(?:ALA)?\.?|SCALE)\s*:?\s*)?(1\s*[:/]\s*\d+(?:[.,]\d+)?)$"
    )
    PAIR_LABEL: ClassVar[Pattern[str]] = re.compile(r"^([A-Z0-9]{1,3})\s*[-–]\s*\1$")
    BUBBLE_LABEL: ClassVar[Pattern[str]] = re.compile(r"^[A-Z0-9]{1,3}$")
    MARKER_BLOCK_PATTERNS: ClassVar[List[Tuple[Pattern[str], DrawingViewKind]]] = [
        (re.compile(r"(CORTE|SECTION|SECAO|CUT)"), DrawingViewKind.SECTION_VIEW),
        (re.compile(r"(ELEV|FACHADA)"), DrawingViewKind.ELEVATION_VIEW),
        (re.compile(r"(DETALHE|DETAIL|DET[_\- ]|BUBBLE|BOLHA)"), DrawingViewKind.DETAIL_VIEW),
    ]
    FRAME_BLOCK_PATTERN: ClassVar[Pattern[str]] = re.compile(
        r"(MOLDURA|FRAME|BORDA|BORDER|VIEW[_\- ]?BOX)"
    )
    TITLE_BLOCK_WORDS: ClassVar[Tuple[str, ...]] = (
        "CARIMBO",
        "PRANCHA",
        "FOLHA",
        "PROPRIETARIO",
        "RESPONSAVEL",
        "AUTOR",
        "REVISAO",
        "DATA:",
        "SHEET",
        "DRAWN BY",
        "CHECKED BY",
        "PROJECT NO",
    )
    TITLE_BLOCK_MIN_WORDS: ClassVar[int] = 2
    MAX_TITLE_LENGTH: ClassVar[int] = 80

    @classmethod
    def normalized(cls, text: str) -> str:
        """Upper-case, unaccented text with single spaces."""
        decomposed: str = unicodedata.normalize("NFKD", text)
        unaccented: str = "".join(
            character
            for character in decomposed
            if unicodedata.category(character) != "Mn"
        )
        return " ".join(unaccented.upper().split())

    @classmethod
    def kind_of_title(cls, text: str) -> Optional[DrawingViewKind]:
        normalized: str = cls.normalized(text)
        if len(normalized) > cls.MAX_TITLE_LENGTH:
            return None
        pattern: Pattern[str]
        kind: DrawingViewKind
        for pattern, kind in cls.TITLE_PATTERNS:
            if pattern.search(normalized):
                return kind
        return None

    @classmethod
    def scale_in(cls, text: str) -> Optional[str]:
        match: Optional[re.Match[str]] = cls.SCALE_IN_TEXT.search(cls.normalized(text))
        if match is None:
            return None
        return cls._scale(match.group(1))

    @classmethod
    def scale_only(cls, text: str) -> Optional[str]:
        match: Optional[re.Match[str]] = cls.SCALE_ONLY.match(cls.normalized(text))
        if match is None:
            return None
        return cls._scale(match.group(1))

    @classmethod
    def title_without_scale(cls, text: str) -> str:
        """The title as written, without the scale written in the same text."""
        single_spaced: str = " ".join(text.split())
        match: Optional[re.Match[str]] = cls.SCALE_IN_TEXT.search(
            cls.normalized(single_spaced)
        )
        if match is None:
            return single_spaced
        # Normalization keeps one character per character of single-spaced
        # text for the scripts titles are written in, so the span applies.
        return single_spaced[: match.start()].rstrip(" -–—,;")

    @classmethod
    def is_pair_label(cls, text: str) -> bool:
        return cls.PAIR_LABEL.match(cls.normalized(text)) is not None

    @classmethod
    def is_bubble_label(cls, text: str) -> bool:
        return cls.BUBBLE_LABEL.match(cls.normalized(text)) is not None

    @classmethod
    def marker_kind_of_block(cls, block_name: str) -> Optional[DrawingViewKind]:
        normalized: str = cls.normalized(block_name)
        pattern: Pattern[str]
        kind: DrawingViewKind
        for pattern, kind in cls.MARKER_BLOCK_PATTERNS:
            if pattern.search(normalized):
                return kind
        return None

    @classmethod
    def is_frame_block(cls, block_name: str) -> bool:
        return cls.FRAME_BLOCK_PATTERN.search(cls.normalized(block_name)) is not None

    @classmethod
    def is_title_block(cls, texts: List[str]) -> bool:
        """Whether these texts read as a sheet's title block, not as a view."""
        words: int = 0
        word: str
        for word in cls.TITLE_BLOCK_WORDS:
            if any(word in cls.normalized(text) for text in texts):
                words += 1
        return words >= cls.TITLE_BLOCK_MIN_WORDS

    @staticmethod
    def _scale(raw: str) -> str:
        return "".join(raw.split()).replace("/", ":")
