from typing import Any, ClassVar, Optional

from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from infobim.context.adapter.kind import OntologyKindResolver
from infobim.context.domain.port.kind import KindResolverPort

from infobim.context.adapter.taxonomy import PARAMETER_KEY

class KindStrategy(CliContextStrategyPort):
    SELECTOR_FLAG: ClassVar[str] = "--kind"
    METADATA: ParameterMetadata = ParameterMetadata(
        id="org.infobim.context.plugin.parameter.kind",
        version="1.0.0",
        name="element_kind",
        description="Resolve --kind across all kind ontologies to a concept URI.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
        tags=["infobim", "kind", "ontology"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self, resolver: Optional[KindResolverPort] = None) -> None:
        self._resolver: KindResolverPort = (
            OntologyKindResolver() if resolver is None else resolver
        )

    def execute(self, context: CliContextPort) -> CliContextPort:
        if self.SELECTOR_FLAG not in context.raw_args:
            context.delete_parameter(PARAMETER_KEY)
            return context

        supplied: Any = context.get_parameter_value(PARAMETER_KEY)
        if not isinstance(supplied, str) or not supplied.strip():
            raise CliCommandArgumentException("--kind requires a non-empty value.")

        try:
            resolved: str = self._resolver.resolve(supplied)
        except ValueError as error:
            raise CliCommandArgumentException(str(error)) from error

        context.set_parameter_value(PARAMETER_KEY, resolved)

        return context
