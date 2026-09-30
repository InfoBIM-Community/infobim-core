import unicodedata
from functools import lru_cache
from typing import Any, ClassVar, List, Optional, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter, OntologyResourceLocator
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.ontology import OntologyConfigPort
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort

from infobim.dict.domain.exception.dictionary import (
    DictionaryPrefixNotRegisteredError,
)
from infobim.dict.plugin.machine.dictionary_entity_create.state import (
    DictionaryEntityContextKeys,
)


try:  # pragma: no cover - stanza is a heavy optional dep; import guards match path_lemmatized
    import stanza
    from stanza import Pipeline
    from stanza.models.common.doc import Document, Sentence, Word
except Exception:  # pragma: no cover
    stanza = None  # type: ignore[assignment]

    class Pipeline:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "Stanza is not available. Install stanza to use --kind."
            )

    Document = None  # type: ignore[assignment,misc]
    Sentence = None  # type: ignore[assignment,misc]
    Word = None  # type: ignore[assignment,misc]


class KindStrategy(CliContextStrategyPort):
    """
    Resolves what ``--kind`` names to where its dictionary entry lives.

    The pipeline is deliberately strict and never guesses. A free-form kind
    string is lemmatized (using the exact stanza pipeline the FSM already
    uses for file meaning), joined into PascalCase, normalized by stripping
    diacritics, and compared *exactly* against ``skos:altLabel`` literals
    carried by every AECO class in ``aeco/kind.ttl``. Zero matches or more
    than one match are both reported as explicit failures: this strategy
    is a resolver, not a search engine.

    Once the AECO class is resolved, the matching dictionary entity TTL is
    found by walking every registered InfoBIM entity prefix and looking
    for the OWL restriction that declares ``aeco:<Kind>`` is represented
    (``crm:P138i_has_representation``) by a local representation class.
    The document that declares that restriction is the entry the run will
    define the element from, and its filesystem path is bound under the
    same dictionary URI key the previous resolver used, so the machine
    downstream never changes its contract.
    """

    SELECTOR_FLAG: ClassVar[str] = "--kind"
    PARAMETER_KEY: ClassVar[str] = (
        DictionaryEntityContextKeys.DICTIONARY_URI_KEY
    )
    KIND_KEY: ClassVar[str] = DictionaryEntityContextKeys.KIND_KEY
    AECO_CLASS_KEY: ClassVar[str] = DictionaryEntityContextKeys.AECO_CLASS_URI_KEY

    ENTRY_TYPE: ClassVar[str] = "type"

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.infobim.dict.plugin.parameter.kind",
        version="1.0.0",
        name="kind",
        description=(
            "Resolve the dictionary entry a --kind names by lemmatizing the "
            "free-form string, joining its lemmas in PascalCase, and matching "
            "the result against the AECO kind ontology."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
        tags=["infobim", "dict", "dictionary", "ontology", "kind", "nlp"],
        supported_languages=["en", "pt-br"],
    )

    # CIDOC CRM P138i: inverse of P138_represents. Declared inline instead of
    # pulling a full prefix registry because this strategy only needs the URI
    # string to build the rdflib URIRef for restriction walking.
    _CRM_P138I_HAS_REPRESENTATION: ClassVar[URIRef] = URIRef(
        "http://www.cidoc-crm.org/cidoc-crm/P138i_has_representation"
    )

    _LANGUAGES: ClassVar[Tuple[str, ...]] = ("pt-br", "en")

    # Stop-words dropped from the whitespace-tokenized fallback so inputs
    # like "Pia de cozinha" and "Kitchen sink" collapse to the PascalCase
    # identifier ("PiaDeCozinha", "KitchenSink") the catalog carries.
    _STOPWORDS: ClassVar[set] = frozenset({
        # Portuguese: articles, prepositions, contractions commonly found in
        # user-written kind strings.
        "o", "os", "a", "as", "um", "uma", "uns", "umas",
        "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
        "por", "pelo", "pela", "pelos", "pelas",
        "e", "ou", "com", "sem", "para", "pra", "pro",
        # English: articles, particles and prepositions.
        "a", "an", "the",
        "of", "in", "on", "at", "to", "for", "with", "without", "by",
        "and", "or", "as", "is", "are",
    })

    def __init__(self, ontology: Optional[OntologyConfigPort] = None) -> None:
        self._ontology: OntologyConfigPort = ontology or OntologyConfigAdapter(
            config_adapter=UnsetProjectRootConfigDataAdapter(),
        )

    def execute(self, context: CliContextPort) -> CliContextPort:
        """
        Bind where the named kind's dictionary entry is read from.

        As with the previous URI strategy, only a flag this invocation
        actually carries counts. The context outlives a command and writes
        strings to ``context.ttl``, so a kind resolved for an earlier run
        would otherwise be re-resolved as if the current run had typed it.
        """
        if self.SELECTOR_FLAG not in context.raw_args:
            return context

        stated: Any = context.get_parameter_value(self.KIND_KEY)
        if not isinstance(stated, str) or not stated.strip():
            return context

        raw_kind: str = stated.strip()
        context.set_parameter_value(self.KIND_KEY, raw_kind)

        candidates: List[str] = self._canonical_candidates(raw_kind)
        aeco_class_uri: URIRef = self._resolve_aeco_class(candidates, raw_kind)
        context.set_parameter_value(self.AECO_CLASS_KEY, str(aeco_class_uri))

        entry_path: str = self._resolve_entity_entry(aeco_class_uri, raw_kind)
        context.set_parameter_value(self.PARAMETER_KEY, entry_path)
        context.delete_parameter(DictionaryEntityContextKeys.DICTIONARY_NAMESPACE_KEY)

        return context

    def _canonical_candidates(self, raw_kind: str) -> List[str]:
        """
        Return multiple canonicalized PascalCase forms of ``raw_kind`` so
        stanza lemmatization quirks (gender endings, dropped particles) do
        not break a match against the catalog. The returned candidates are
        unique, diacritic-folded and ordered from most authoritative to
        most heuristic:

        1. Stanza-lemmatized form (per supported language, longest wins).
        2. Whitespace-tokenized, capitalized, stop-words stripped.
        3. Whitespace-tokenized, capitalized, stop-words kept.
        """
        seen: set = set()
        out: List[str] = []

        stanza_candidate: Optional[str] = self._best_stanza_canonical(raw_kind)
        if stanza_candidate is not None and stanza_candidate not in seen:
            seen.add(stanza_candidate)
            out.append(stanza_candidate)

        raw_tokens: List[str] = [
            token for token in raw_kind.strip().split() if token.strip()
        ]
        filtered_tokens: List[str] = [
            token for token in raw_tokens
            if token.strip().lower() not in self._STOPWORDS
        ]

        for token_pool in (filtered_tokens, raw_tokens):
            if not token_pool:
                continue
            pascal: str = "".join(
                t[:1].upper() + t[1:]
                for t in (self._fold_diacritics(tok).lower() for tok in token_pool)
                if t
            )
            if pascal and pascal not in seen:
                seen.add(pascal)
                out.append(pascal)

        if not out:
            raise KindLemmatizationError(
                f"The value supplied to --kind ('{raw_kind}') produced no "
                f"usable canonical candidates in any supported path."
            )
        return out

    def _best_stanza_canonical(self, raw_kind: str) -> Optional[str]:
        """Return the stanza-lemmatized PascalCase form (longest, i.e. most
        token-rich) across every supported language, or ``None`` when
        stanza produces no usable lemmas at all."""
        best: Optional[str] = None
        language: str
        for language in self._LANGUAGES:
            lemmas: List[str] = self._lemmas(raw_kind, language)
            if not lemmas:
                continue
            pascal: str = "".join(
                lemma[:1].upper() + lemma[1:] for lemma in lemmas
            )
            folded: str = self._fold_diacritics(pascal)
            if best is None or len(folded) > len(best):
                best = folded
        return best

    def _resolve_aeco_class(
        self,
        candidates: List[str],
        raw_kind: str,
    ) -> URIRef:
        """
        Try every candidate in order against the AECO kind graph's
        ``skos:altLabel`` values. When a candidate matches, that match is
        returned immediately. Multiple different classes matching are
        reported as ambiguous UNLESS the matched set is a clique of pairwise
        ``owl:equivalentClass`` subjects — in which case any one of them is
        semantically identical and the first is returned deterministically.
        """
        graph: Graph = self._kind_graph()
        resolved: List[URIRef] = []
        for candidate in candidates:
            matches_here: List[URIRef] = []
            subject: URIRef
            literal: Literal
            for subject, literal in graph.subject_objects(SKOS.altLabel):
                if not isinstance(subject, URIRef):
                    continue
                if not isinstance(literal, Literal):
                    continue
                value: str = self._fold_diacritics(str(literal))
                if value == candidate:
                    matches_here.append(subject)
            unique_here: List[URIRef] = list(
                {uri.n3(): uri for uri in matches_here}.values()
            )
            if len(unique_here) == 0:
                continue
            if len(unique_here) == 1:
                resolved.append(unique_here[0])
                continue
            if self._is_equivalent_clique(graph, unique_here):
                resolved.append(unique_here[0])
                continue
            rendered: str = ", ".join(
                sorted(uri.n3() for uri in unique_here)
            )
            raise AmbiguousKindMatchError(
                f"--kind '{raw_kind}' is ambiguous: the canonical form "
                f"'{candidate}' matches {len(unique_here)} distinct AECO "
                f"classes that are NOT all mutually equivalent ({rendered}). "
                f"Narrow the spelling so it matches exactly one class."
            )

        unique_resolved: List[URIRef] = list(
            {uri.n3(): uri for uri in resolved}.values()
        )
        if len(unique_resolved) == 0:
            tried_repr: str = ", ".join(repr(c) for c in candidates)
            raise KindNotMatchedError(
                f"No AECO class matches --kind '{raw_kind}'. Tried "
                f"canonical forms: {tried_repr}. Add a matching "
                f"skos:altLabel to the class in aeco/kind.ttl, or check "
                f"the spelling and try again."
            )
        if len(unique_resolved) == 1:
            return unique_resolved[0]
        if self._is_equivalent_clique(graph, unique_resolved):
            return unique_resolved[0]
        rendered: str = ", ".join(sorted(uri.n3() for uri in unique_resolved))
        raise AmbiguousKindMatchError(
            f"--kind '{raw_kind}' is ambiguous: different canonical forms "
            f"resolve to NON-equivalent AECO classes ({rendered}). "
            f"Narrow the spelling."
        )

    def _resolve_entity_entry(self, aeco_class_uri: URIRef, raw_kind: str) -> str:
        """
        Reverse-map a resolved AECO class URI into the dictionary entity TTL
        that declares its representation via ``crm:P138i_has_representation``.

        Because PT/EN sibling classes linked by ``owl:equivalentClass`` may
        split the declaration (the EN side declares the representation link
        while the PT side is what the user's kind string matched), the
        entire transitive equivalent-class clique is walked before giving
        up.
        """
        registry: Any = OntologyResourceLocator._PREFIX_TO_RESOURCE_PARTS
        infobim_entity_prefixes: List[Tuple[str, Tuple[str, ...]]] = [
            (prefix, parts)
            for prefix, parts in registry.items()
            if len(parts) >= 3 and parts[0] == "tool" and parts[1] == "infobim" and parts[2] == "entity"
        ]

        clique: List[URIRef] = self._equivalent_class_clique(
            self._kind_graph(), aeco_class_uri
        )

        prefix: str
        parts: Tuple[str, ...]
        for prefix, parts in infobim_entity_prefixes:
            try:
                entry_file: str = self._ontology.get_ontology_path(
                    prefix, self.ENTRY_TYPE
                )
            except FileNotFoundError:
                continue

            g: Graph = Graph()
            try:
                g.parse(entry_file, format="turtle")
            except Exception:
                continue
            member: URIRef
            for member in clique:
                if self._graph_has_p138i_restriction(g, member):
                    return entry_file

        rendered_clique: str = ", ".join(sorted(uri.n3() for uri in clique))
        raise KindHasNoDictionaryEntryError(
            f"The AECO class <{aeco_class_uri}> (equivalent-class clique: "
            f"{rendered_clique}) matched by --kind '{raw_kind}' is not "
            f"represented by any registered InfoBIM dictionary entity "
            f"document. Register a new entity prefix that links one of "
            f"these classes to an IFC representation via "
            f"crm:P138i_has_representation."
        )

    @classmethod
    def _graph_has_p138i_restriction(cls, graph: Graph, aeco_class_uri: URIRef) -> bool:
        """
        Return whether ``graph`` declares ``aeco_class_uri`` as a subject of
        an ``rdfs:subClassOf`` restriction whose onProperty is the CIDOC CRM
        inverse-represents property.
        """
        restriction: URIRef
        for restriction in graph.objects(aeco_class_uri, RDFS.subClassOf):
            if not isinstance(restriction, URIRef) and not hasattr(restriction, "toPython"):
                continue
            on_prop_obj: List[Any] = list(graph.objects(restriction, OWL.onProperty))
            if not on_prop_obj:
                continue
            if cls._CRM_P138I_HAS_REPRESENTATION in on_prop_obj:
                return True
        return False

    @classmethod
    def _equivalent_class_clique(cls, graph: Graph, seed: URIRef) -> List[URIRef]:
        """Return the transitive reflexive closure of ``owl:equivalentClass``
        reachable from ``seed``, deduplicated and deterministically sorted.
        """
        visited: Dict[str, URIRef] = {seed.n3(): seed}
        stack: List[URIRef] = [seed]
        while stack:
            current: URIRef = stack.pop()
            for obj in graph.objects(current, OWL.equivalentClass):
                if not isinstance(obj, URIRef):
                    continue
                key: str = obj.n3()
                if key in visited:
                    continue
                visited[key] = obj
                stack.append(obj)
            for subj in graph.subjects(OWL.equivalentClass, current):
                    if not isinstance(subj, URIRef):
                        continue
                    key = subj.n3()
                    if key in visited:
                        continue
                    visited[key] = subj
                    stack.append(subj)
        return sorted(visited.values(), key=lambda u: u.n3())

    @classmethod
    def expand_equivalent_clique(cls, aeco_class_uri: str) -> List[str]:
        """
        Return the AECO kind URI plus every node reachable from it via
        transitive ``owl:equivalentClass`` links, as plain strings.

        The CLI context adapter persists a single scalar URI for
        ``aeco_class_uri`` (lists are non-serializable through its RDF
        backing), so consumers that need the whole semantic clique
        (notably the P138 narrowing that picks the one representation
        out of a multi-type entry) walk the equivalent-class graph once
        here instead of requiring the strategy to push a list upstream.
        ``kind_graph`` is LRU-cached so repeated calls are cheap.
        """
        stripped: str = aeco_class_uri.strip()
        if not stripped:
            return []
        graph: Graph = cls.kind_graph()
        seed: URIRef = URIRef(stripped)
        clique: List[URIRef] = cls._equivalent_class_clique(graph, seed)
        return [str(uri) for uri in clique]

    @classmethod
    @lru_cache(maxsize=1)
    def kind_graph(cls) -> Graph:
        """
        Load and cache the AECO kind graph (``aeco/kind.ttl``).

        This is a class-level LRU-cached variant (mirror of the instance
        helper) so equivalent-class cliques can be expanded from static
        consumers without instantiating a full strategy or ontology
        adapter every time a state needs to narrow by representation.
        Errors are reported with the same dictionary-facing surface the
        instance method uses, so CLI error messages stay consistent.
        """
        ontology: OntologyConfigPort = OntologyConfigAdapter(
            UnsetProjectRootConfigDataAdapter()
        )
        try:
            graph: Graph = ontology.get_ontology_content("aeco", "kind")
        except FileNotFoundError as error:
            raise DictionaryPrefixNotRegisteredError(
                "The AECO kind ontology (aeco/kind.ttl) could not be loaded, "
                "so --kind cannot resolve any value. Make sure the aeco prefix "
                f"is registered and present. ({error})"
            ) from error
        return graph

    @classmethod
    def _is_equivalent_clique(cls, graph: Graph, nodes: List[URIRef]) -> bool:
        """Return True if every pair of ``nodes`` is in the same transitive
        ``owl:equivalentClass`` clique."""
        if len(nodes) <= 1:
            return True
        clique: set = {u.n3() for u in cls._equivalent_class_clique(graph, nodes[0])}
        return all(u.n3() in clique for u in nodes[1:])

    def _kind_graph(self) -> Graph:
        """
        Load the AECO kind graph once per strategy instance. Fail with a
        dictionary-facing error if the adapter cannot resolve it, so the
        CLI surface reports a cause instead of a FileNotFound.
        """
        try:
            graph: Graph = self._ontology.get_ontology_content("aeco", "kind")
        except FileNotFoundError as error:
            raise DictionaryPrefixNotRegisteredError(
                "The AECO kind ontology (aeco/kind.ttl) could not be loaded, "
                "so --kind cannot resolve any value. Make sure the aeco prefix "
                f"is registered and present. ({error})"
            ) from error
        return graph

    @classmethod
    def _lemmas(cls, value: str, language: str) -> List[str]:
        """
        Tokenize + lemmatize using the stanza pipeline, skipping punctuation
        and canonicalizing tokens to lowercase. Signature mirrors the
        ``path_lemmatized`` capability's own helper so behaviour stays
        identical across both call sites.
        """
        if stanza is None:
            raise RuntimeError(
                "Stanza is not available. Install stanza to use --kind."
            )
        pipeline: Pipeline = cls._language_pipeline(language)
        document: Document = pipeline(value)
        lemmas: List[str] = []
        sentence: Sentence
        for sentence in document.sentences:
            word: Word
            for word in sentence.words:
                if word.upos == "PUNCT":
                    continue
                lemma: Optional[str] = word.lemma
                if not isinstance(lemma, str) or not lemma.strip():
                    raise ValueError(
                        f"Stanza returned no lemma for token '{word.text}' "
                        f"in --kind value '{value}'."
                    )
                lemmas.append(lemma.strip().lower())
        return lemmas

    @classmethod
    @lru_cache(maxsize=8)
    def _language_pipeline(cls, language: str) -> Pipeline:  # pragma: no cover - stanza caching
        normalized: str = language.strip().lower().split("-", 1)[0]
        if stanza is None:
            raise RuntimeError(
                "Stanza is not available. Install stanza to use --kind."
            )
        return stanza.Pipeline(
            lang=normalized,
            processors="tokenize,mwt,pos,lemma",
            verbose=False,
        )

    @staticmethod
    def _fold_diacritics(value: str) -> str:
        """
        Return ``value`` decomposed with any combining diacritical marks
        stripped, so ``BaciaSanitária`` (acute-a) and ``BaciaSanitaria``
        (ASCII) collapse to the same canonical string for exact matching.
        """
        decomposed: str = unicodedata.normalize("NFKD", value)
        stripped: str = "".join(
            character for character in decomposed
            if unicodedata.category(character) != "Mn"
        )
        return stripped


class KindStrategyError(DictionaryPrefixNotRegisteredError):
    """Base class for all failures raised by KindStrategy so callers can
    discriminate resolver-specific errors from generic dictionary errors."""


class KindLemmatizationError(KindStrategyError):
    """Raised when a --kind value yields no usable lemmas."""


class KindNotMatchedError(KindStrategyError):
    """Raised when a canonical --kind form matches zero AECO classes."""


class AmbiguousKindMatchError(KindStrategyError):
    """Raised when a canonical --kind form matches more than one AECO class."""


class KindHasNoDictionaryEntryError(KindStrategyError):
    """Raised when a resolved AECO class is not linked to any entity TTL."""
