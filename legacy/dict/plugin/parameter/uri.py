import re
from typing import Any, ClassVar, Optional, Pattern

from rdflib.namespace import Namespace

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.ontology import OntologyConfigPort
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort

from infobim.dict.domain.exception.dictionary import (
    DictionaryPrefixNotRegisteredError,
)
from infobim.dict.plugin.machine.dictionary_entity_create.state import (
    DictionaryEntityContextKeys,
)


class UriStrategy(CliContextStrategyPort):
    """
    Resolves what ``--uri`` names to where that document can be read.

    A dictionary entry has two names: the namespace it is published
    under, which is long and is what the entry *is*, and the prefix every
    tool in this stack already calls it by, which is short and is what
    people type. Both arrive through the same flag, and this is where the
    second becomes the first.

    Expansion is a lookup, never a rule over spelling. Which prefix is
    short for which document is declared centrally, in the ontology
    adapter every tool resolves through, so a prefix nobody declared is
    reported as unknown instead of being turned into a path by
    substituting its own characters into a layout — a guess like that
    reads whatever file happens to sit where it pointed.

    What is bound back is the location the entry is read from: the
    packaged copy of the ontology tree, which is the canonical one and is
    there whether or not the machine has a network. The namespace the
    prefix names is bound beside it, because after the expansion it is
    the only remaining record of what was asked for.

    A value that is not a prefix is left exactly as it arrived. A URL, a
    ``file://`` URI and a path are already locations, and a second
    opinion about them here would be this strategy deciding something the
    caller had already decided.
    """

    SELECTOR_FLAG: ClassVar[str] = "--uri"
    PARAMETER_KEY: ClassVar[str] = (
        DictionaryEntityContextKeys.DICTIONARY_URI_KEY
    )
    NAMESPACE_KEY: ClassVar[str] = (
        DictionaryEntityContextKeys.DICTIONARY_NAMESPACE_KEY
    )

    # A dictionary entry is the "type" document of an entity prefix --
    # tool/infobim/entity/ifc_sanitary_terminal_type.ttl is what
    # bsi_element_ifc_sanitary_terminal is short for. Other documents of
    # the same prefix are other things, and naming one of those is naming
    # it in full.
    ENTRY_TYPE: ClassVar[str] = "type"

    # A prefix is a bare token: that is the shape every declared prefix
    # has, and it is what tells one from a location without probing the
    # filesystem for a value the caller meant as a URL.
    PREFIX_PATTERN: ClassVar[Pattern[str]] = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")

    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.infobim.dict.plugin.parameter.uri",
        version="1.0.0",
        name="dictionary_uri",
        description=(
            "Resolve the dictionary entry a --uri names, expanding a declared "
            "ontology prefix into the document it is short for."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
        tags=["infobim", "dict", "dictionary", "ontology", "prefix"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self, ontology: Optional[OntologyConfigPort] = None) -> None:
        self._ontology: OntologyConfigPort = ontology or OntologyConfigAdapter(
            config_adapter=UnsetProjectRootConfigDataAdapter(),
        )

    def execute(self, context: CliContextPort) -> CliContextPort:
        """
        Bind where the named entry is read from, expanding a prefix first.

        Only a flag this invocation actually carries counts. The context
        outlives a command and writes strings to ``context.ttl``, so a
        dictionary resolved for an earlier run is still sitting there,
        and expanding it again would answer this run with the last one's
        entry.
        """
        if self.SELECTOR_FLAG not in context.raw_args:
            return context

        stated: Any = context.get_parameter_value(self.PARAMETER_KEY)
        if not isinstance(stated, str) or not stated.strip():
            return context

        value: str = stated.strip()
        if self.PREFIX_PATTERN.match(value) is None:
            self._forget_namespace(context)

            return context

        context.set_parameter_value(self.PARAMETER_KEY, self._entry_of(value))
        self._bind_namespace(context, value)

        return context

    def _entry_of(self, prefix: str) -> str:
        """
        Return where the entry the prefix names is read from.
        """
        try:
            return self._ontology.get_ontology_path(prefix, self.ENTRY_TYPE)
        except FileNotFoundError as error:
            raise DictionaryPrefixNotRegisteredError(
                f"'{prefix}' names no dictionary entry: no ontology is "
                f"declared for that prefix, or it declares no "
                f"'{self.ENTRY_TYPE}' document. Name the entry in full, or "
                f"declare the prefix where every tool resolves prefixes "
                f"({error})."
            ) from error

    def _bind_namespace(self, context: CliContextPort, prefix: str) -> None:
        """
        Bind the namespace the prefix names, when one is declared for it.

        A prefix may name a document without naming a namespace: the two
        are separate declarations, and a missing namespace is not a
        reason to refuse an entry that resolved. What it must never be is
        the previous run's namespace, so the key is dropped rather than
        left standing.
        """
        namespace: Optional[Namespace] = self._ontology.get_ontology_namespace_by_prefix(
            prefix
        )
        if namespace is None:
            self._forget_namespace(context)

            return

        context.set_parameter_value(self.NAMESPACE_KEY, str(namespace))

    def _forget_namespace(self, context: CliContextPort) -> None:
        """
        Drop the namespace an earlier invocation expanded.
        """
        context.delete_parameter(self.NAMESPACE_KEY)
